import time
import uuid
from collections.abc import Callable

import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from jwt import PyJWKClient
from jwt import encode as jwt_encode
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import RoleFactory, SsoProviderFactory, SsoRoleMappingFactory
from vmss_api.auth.models import AuditLog, Role, User
from vmss_api.auth.repository import UserRepository
from vmss_api.core import encryption
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import decode_token
from vmss_api.sso import oidc_client
from vmss_api.sso import service as sso_service
from vmss_api.sso.models import SsoProvider
from vmss_api.tenant.models import Tenant

# --- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sso_settings(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "sso_encryption_key", Fernet.generate_key().decode())
    encryption._fernet.cache_clear()
    monkeypatch.setattr(
        settings, "sso_redirect_uri", "https://api.acme-test.example/api/v1/auth/sso/callback"
    )
    monkeypatch.setattr(
        settings, "sso_frontend_callback_url", "https://portal.acme-test.example/sso/callback"
    )


@pytest.fixture
async def host_role(db_session: AsyncSession) -> Role:
    role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest.fixture
async def security_role(db_session: AsyncSession) -> Role:
    role = RoleFactory.build(id=uuid.uuid4(), name="security", permissions=[])
    db_session.add(role)
    await db_session.commit()
    return role


_current_jwks: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def _stub_jwk_fetch(monkeypatch):
    """`jwt.PyJWKClient.fetch_data` calls `urllib.request.urlopen` directly
    (not `httpx`), so `respx` can never intercept it — confirmed the hard
    way: a real DNS lookup for a fake `*.example.com` host is what a
    naive respx-only mock actually triggered here. Stubbed via
    `monkeypatch` instead, keyed by the client's own `uri` so multiple
    fake IdPs in the same test suite don't collide.
    """
    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda self: _current_jwks[self.uri])
    _current_jwks.clear()
    yield
    _current_jwks.clear()


@pytest.fixture(autouse=True)
def _stub_dns_resolution(monkeypatch):
    """`oidc_client._assert_safe_outbound_url` (the SSRF guard) resolves
    every discovery URL's host via real DNS — but every test's fake IdP
    host (`idp-<random>.example.com`) doesn't actually resolve, so without
    this stub every SSO test would fail on `UnsafeDiscoveryUrlError`
    ("Could not resolve host"), not on whatever it's actually testing.
    Defaults to a safe public IP; the SSRF-specific tests below override
    this per-test to a private/loopback address to prove rejection.
    """
    monkeypatch.setattr(oidc_client, "_resolve_host_ips", lambda hostname: ["93.184.216.34"])


def _idp_urls() -> dict[str, str]:
    """A fresh, unique-per-test set of fake IdP endpoints — see design.md's
    testing notes: reusing one fixed URL across tests risks `PyJWKClient`'s
    internal key cache (keyed by JWKS URI) serving a stale key from an
    earlier test's differently-generated RSA keypair.
    """
    base = f"https://idp-{uuid.uuid4().hex[:12]}.example.com"
    return {
        "discovery": f"{base}/.well-known/openid-configuration",
        "authorization": f"{base}/authorize",
        "token": f"{base}/token",
        "jwks": f"{base}/keys",
        "issuer": f"{base}/",
    }


def _rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_document(private_key: rsa.RSAPrivateKey, kid: str) -> dict:
    jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def _sign_id_token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str,
    issuer: str,
    audience: str,
    nonce: str,
    email: str,
    name: str = "Test User",
    groups: list[str] | None = None,
    expires_in: int = 300,
) -> str:
    now = int(time.time())
    claims: dict = {
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
        "nonce": nonce,
        "email": email,
        "name": name,
    }
    if groups is not None:
        claims["groups"] = groups
    return jwt_encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _register_discovery_and_jwks(
    urls: dict[str, str], *, jwks: dict, discovery_unreachable: bool = False
) -> None:
    """Registers everything the login-*initiate* step needs
    (`start_login` fetches the discovery document to build the
    authorization URL) — split from `_register_token_endpoint` below
    because the token endpoint's response depends on the `nonce` the
    initiate step hands back, which isn't known until after this call.
    The JWKS document itself is served via `_current_jwks`
    (`_stub_jwk_fetch` above), not a respx route — see that fixture's
    docstring for why.
    """
    if discovery_unreachable:
        respx.get(urls["discovery"]).mock(side_effect=httpx.ConnectError("connection refused"))
        return

    respx.get(urls["discovery"]).mock(
        return_value=httpx.Response(
            200,
            json={
                "issuer": urls["issuer"],
                "authorization_endpoint": urls["authorization"],
                "token_endpoint": urls["token"],
                "jwks_uri": urls["jwks"],
            },
        )
    )
    _current_jwks[urls["jwks"]] = jwks


def _register_token_endpoint(
    urls: dict[str, str],
    *,
    id_token: str | None = None,
    client_credentials_error: str | None = None,
) -> None:
    def _token_response(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if "grant_type=client_credentials" in body:
            if client_credentials_error:
                return httpx.Response(400, json={"error": client_credentials_error})
            return httpx.Response(200, json={"access_token": "fake", "token_type": "Bearer"})
        return httpx.Response(200, json={"id_token": id_token})

    respx.post(urls["token"]).mock(side_effect=_token_response)


def _register_idp(
    urls: dict[str, str],
    *,
    jwks: dict,
    id_token: str | None = None,
    client_credentials_error: str | None = None,
    discovery_unreachable: bool = False,
) -> None:
    """Convenience for tests that hit a single endpoint needing the full
    IdP surface registered up front (e.g. the config "test connection"
    check) — the login-initiate/callback flow needs the two-phase split
    above instead.
    """
    _register_discovery_and_jwks(urls, jwks=jwks, discovery_unreachable=discovery_unreachable)
    if discovery_unreachable:
        return
    _register_token_endpoint(
        urls, id_token=id_token, client_credentials_error=client_credentials_error
    )


async def _save_provider(
    db_session: AsyncSession, *, discovery_url: str, client_id: str, client_secret: str
) -> SsoProvider:
    provider = SsoProviderFactory.build(
        id=uuid.uuid4(),
        display_name="Test IdP",
        discovery_url=discovery_url,
        client_id=client_id,
        client_secret_encrypted=encryption.encrypt(client_secret),
        client_secret_masked=encryption.mask_secret(client_secret),
        is_enabled=True,
        deleted_at=None,
    )
    db_session.add(provider)
    await db_session.commit()
    return provider


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


async def _do_sso_login(
    client: AsyncClient,
    *,
    tenant_slug: str,
    urls: dict[str, str],
    private_key: rsa.RSAPrivateKey,
    kid: str,
    client_id: str,
    email: str,
    name: str = "Test User",
    groups: list[str] | None = None,
    expires_in: int = 300,
) -> httpx.Response:
    """Drives login-initiate -> callback, returning the callback's raw
    (redirect) response so each test can assert on it directly. Discovery/
    JWKS are registered before `initiate` (which fetches the discovery
    document itself); the token endpoint is only registered afterward,
    once the server-generated `nonce` needed to sign a matching ID token
    is known.
    """
    _register_discovery_and_jwks(urls, jwks=_jwks_document(private_key, kid))

    initiate = await client.get(f"/api/v1/auth/sso/{tenant_slug}/login")
    assert initiate.status_code == 307, initiate.text
    location = httpx.URL(initiate.headers["location"])
    state = location.params["state"]
    nonce = location.params["nonce"]

    id_token = _sign_id_token(
        private_key,
        kid=kid,
        issuer=urls["issuer"],
        audience=client_id,
        nonce=nonce,
        email=email,
        name=name,
        groups=groups,
        expires_in=expires_in,
    )
    _register_token_endpoint(urls, id_token=id_token)

    return await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )


# --- Admin configuration: happy path + permission-denied ----------------------


async def test_get_config_not_configured_returns_404(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/sso/config", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_get_config_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/auth/sso/config", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_put_and_get_config_masks_secret(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "displayName": "PIT Solutions",
        "discoveryUrl": "https://login.microsoftonline.com/fake-tenant/v2.0/.well-known/openid-configuration",
        "clientId": "fake-client-id",
        "clientSecret": "super-secret-value-1234",
        "isEnabled": True,
    }
    put_response = await client.put("/api/v1/auth/sso/config", json=payload, headers=headers)
    assert put_response.status_code == 200, put_response.text
    body = put_response.json()["data"]
    assert body["clientSecretMasked"] == "****1234"
    assert "super-secret-value-1234" not in put_response.text

    get_response = await client.get("/api/v1/auth/sso/config", headers=headers)
    assert get_response.status_code == 200
    get_body = get_response.json()["data"]
    assert get_body["clientSecretMasked"] == "****1234"
    assert "super-secret-value-1234" not in get_response.text


async def test_put_config_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.put(
        "/api/v1/auth/sso/config",
        json={
            "displayName": "X",
            "discoveryUrl": "https://idp.example.com/.well-known/openid-configuration",
            "clientId": "x",
            "clientSecret": "x",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@respx.mock
async def test_config_test_connection_success(client: AsyncClient, user: User) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    _register_idp(urls, jwks=_jwks_document(private_key, "kid-1"))
    token = await _login(client, user.email)

    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={"discoveryUrl": urls["discovery"], "clientId": "cid", "clientSecret": "secret"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["success"] is True


@respx.mock
async def test_config_test_connection_invalid_credentials_reports_failure(
    client: AsyncClient, user: User
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    _register_idp(
        urls, jwks=_jwks_document(private_key, "kid-1"), client_credentials_error="invalid_client"
    )
    token = await _login(client, user.email)

    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={"discoveryUrl": urls["discovery"], "clientId": "cid", "clientSecret": "wrong"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["success"] is False


@respx.mock
async def test_config_test_connection_unreachable_discovery_reports_failure(
    client: AsyncClient, user: User
) -> None:
    urls = _idp_urls()
    _register_idp(urls, jwks={}, discovery_unreachable=True)
    token = await _login(client, user.email)

    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={"discoveryUrl": urls["discovery"], "clientId": "cid", "clientSecret": "secret"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["success"] is False


async def test_config_test_connection_rejects_non_https_scheme(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={
            "discoveryUrl": "http://idp.example.com/.well-known/openid-configuration",
            "clientId": "cid",
            "clientSecret": "secret",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["success"] is False
    assert "https" in body["message"].lower()


async def test_config_test_connection_rejects_private_ip_ssrf_attempt(
    client: AsyncClient, user: User, monkeypatch
) -> None:
    """The SSRF guard (design.md's "SSRF guard" decision): a discovery URL
    that resolves to a private/loopback address (e.g. an attempt to reach
    an internal service or a cloud metadata endpoint) is rejected before
    any outbound request is made.
    """
    monkeypatch.setattr(oidc_client, "_resolve_host_ips", lambda hostname: ["169.254.169.254"])
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={
            "discoveryUrl": "https://internal-looking-host.example.com/.well-known/openid-configuration",
            "clientId": "cid",
            "clientSecret": "secret",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["success"] is False
    assert "private" in body["message"].lower() or "reserved" in body["message"].lower()


async def test_config_test_connection_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/sso/config/test",
        json={
            "discoveryUrl": "https://idp.example.com/.well-known/openid-configuration",
            "clientId": "cid",
            "clientSecret": "secret",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- Role mappings: happy path, validation, permission-denied -----------------


async def test_create_list_delete_role_mapping(
    client: AsyncClient, user: User, security_role: Role
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Security-Team", "roleId": str(security_role.id)},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    mapping_id = create_response.json()["data"]["id"]
    assert create_response.json()["data"]["roleName"] == "security"

    list_response = await client.get("/api/v1/auth/sso/role-mappings", headers=headers)
    assert len(list_response.json()["data"]) == 1

    delete_response = await client.delete(
        f"/api/v1/auth/sso/role-mappings/{mapping_id}", headers=headers
    )
    assert delete_response.status_code == 204

    list_after = await client.get("/api/v1/auth/sso/role-mappings", headers=headers)
    assert list_after.json()["data"] == []


async def test_list_role_mappings_sort_by_idp_group_claim_value(
    client: AsyncClient, user: User, host_role: Role, security_role: Role
) -> None:
    """verify-full-api-test-and-validation-coverage task 7.2/7.4 — the
    `sortBy`/`sortOrder` params on `GET /auth/sso/role-mappings`
    (`sso/router.py::list_role_mappings`) are additive-only per
    `api-conventions.md` §2, but had no HTTP-level test proving they
    actually reorder the response.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Zeta-Team", "roleId": str(security_role.id)},
        headers=headers,
    )
    await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Alpha-Team", "roleId": str(host_role.id)},
        headers=headers,
    )

    asc_response = await client.get(
        "/api/v1/auth/sso/role-mappings", params={"sortOrder": "asc"}, headers=headers
    )
    assert [m["idpGroupClaimValue"] for m in asc_response.json()["data"]] == [
        "VMS-Alpha-Team",
        "VMS-Zeta-Team",
    ]

    desc_response = await client.get(
        "/api/v1/auth/sso/role-mappings", params={"sortOrder": "desc"}, headers=headers
    )
    assert [m["idpGroupClaimValue"] for m in desc_response.json()["data"]] == [
        "VMS-Zeta-Team",
        "VMS-Alpha-Team",
    ]


async def test_create_role_mapping_nonexistent_role_returns_404(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "some-group", "roleId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_create_role_mapping_duplicate_group_conflict(
    client: AsyncClient, user: User, security_role: Role, host_role: Role
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"idpGroupClaimValue": "VMS-Security-Team", "roleId": str(security_role.id)}
    first = await client.post("/api/v1/auth/sso/role-mappings", json=payload, headers=headers)
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Security-Team", "roleId": str(host_role.id)},
        headers=headers,
    )
    assert duplicate.status_code == 409


async def test_create_role_mapping_targeting_admin_role_conflict(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    """Mirrors the visitor-role guard above (`test_create_role_mapping_duplicate_group_conflict`
    exercises the group-conflict case) — Admin must never be reachable via
    an SSO-curated mapping. The `user` fixture's own setup already seeded
    the tenant's `admin` role row, so it's queried here rather than
    duplicated.
    """
    admin_role = (await db_session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Admins", "roleId": str(admin_role.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_role_mappings_require_permission(
    client: AsyncClient,
    user_without_permissions: User,
    security_role: Role,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/auth/sso/role-mappings", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_create_role_mapping_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    security_role: Role,
    issue_token: Callable[[User], str],
) -> None:
    """Distinct from the list-endpoint denial above: creating a mapping is
    gated by `sso-config:manage`, not `:view` — a caller denied on `:view`
    doesn't prove `:manage` is actually enforced here.
    """
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Security-Team", "roleId": str(security_role.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_delete_role_mapping_requires_permission(
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    security_role: Role,
    issue_token: Callable[[User], str],
) -> None:
    admin_token = await _login(client, user.email)
    create_response = await client.post(
        "/api/v1/auth/sso/role-mappings",
        json={"idpGroupClaimValue": "VMS-Security-Team", "roleId": str(security_role.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    mapping_id = create_response.json()["data"]["id"]

    other_token = issue_token(user_without_permissions)
    response = await client.delete(
        f"/api/v1/auth/sso/role-mappings/{mapping_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403


async def test_delete_role_mapping_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/auth/sso/role-mappings/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Login flow: happy path, JIT provisioning, role mapping -------------------


@respx.mock
async def test_full_login_flow_creates_account_with_mapped_role(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    security_role: Role,
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    provider = await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    mapping = SsoRoleMappingFactory.build(
        id=uuid.uuid4(),
        idp_group_claim_value="VMS-Security-Team",
        role=security_role,
        deleted_at=None,
    )
    db_session.add(mapping)
    await db_session.commit()

    email = f"new-hire-{uuid.uuid4().hex[:8]}@acme-test.example"
    callback_response = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
        groups=["VMS-Security-Team"],
    )
    assert callback_response.status_code == 307, callback_response.text
    location = httpx.URL(callback_response.headers["location"])
    callback_url = settings.sso_frontend_callback_url
    assert callback_url is not None
    assert str(location).startswith(callback_url)
    exchange_code = location.params["code"]

    exchange_response = await client.post("/api/v1/auth/sso/exchange", json={"code": exchange_code})
    assert exchange_response.status_code == 200, exchange_response.text
    tokens = exchange_response.json()["data"]
    claims = decode_token(tokens["accessToken"])
    assert claims["tenant_id"] == str(tenant.id)

    created_user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    assert str(created_user.id) == claims["sub"]
    assert any(a.role.name == "security" for a in created_user.branch_roles)

    audit_stmt = select(AuditLog.action).where(AuditLog.entity_id == created_user.id)
    audit_actions = (await db_session.execute(audit_stmt)).scalars().all()
    assert "sso_login" in audit_actions
    assert "sso_account_created" in audit_actions
    assert provider.id  # sanity: provider row used above is the one resolved


@respx.mock
async def test_returning_user_reuses_existing_account(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, security_role: Role
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    mapping = SsoRoleMappingFactory.build(
        id=uuid.uuid4(),
        idp_group_claim_value="VMS-Security-Team",
        role=security_role,
        deleted_at=None,
    )
    db_session.add(mapping)
    await db_session.commit()
    email = f"returning-{uuid.uuid4().hex[:8]}@acme-test.example"

    first = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
        groups=["VMS-Security-Team"],
    )
    assert first.status_code == 307

    second = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
        groups=["VMS-Security-Team"],
    )
    assert second.status_code == 307

    users = (await db_session.execute(select(User).where(User.email == email))).scalars().all()
    assert len(users) == 1


async def test_provision_or_resolve_user_concurrent_first_login_resolves_to_one_user(
    db_session: AsyncSession, tenant: Tenant, monkeypatch
) -> None:
    """Regression test for a check-then-act race:
    `sso/service.py::_provision_or_resolve_user` checks `get_by_email` for
    `None`, then inserts a new `User` for a not-yet-provisioned email — two
    concurrent first-time SSO logins for the same email (e.g. a
    double-click on "Sign in with SSO") can both see `None` before either
    commits, and the second's insert then hits `User.email`'s unique
    constraint. Simulated (not a real thread race, matching this
    project's established pattern — see
    `invitations/tests.py::test_approve_invitation_concurrent_requests_
    transition_exactly_once`) by making the second call's own internal
    existence check return a stale `None` even though the first call's
    row has already committed. See
    verify-post-merge-regression-suite/design.md.
    """
    email = f"race-{uuid.uuid4().hex[:8]}@acme-test.example"

    user_a, created_a = await sso_service._provision_or_resolve_user(
        db_session, tenant_id=tenant.id, email=email, full_name="Racer A", groups=[]
    )
    assert created_a is True

    real_get_by_email = UserRepository.get_by_email
    calls = {"n": 0}

    async def stale_read_once(self: UserRepository, email_arg: str) -> User | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get_by_email(self, email_arg)

    monkeypatch.setattr(UserRepository, "get_by_email", stale_read_once)
    user_b, created_b = await sso_service._provision_or_resolve_user(
        db_session, tenant_id=tenant.id, email=email, full_name="Racer B", groups=[]
    )

    assert created_b is False
    assert user_b.id == user_a.id

    users = (await db_session.execute(select(User).where(User.email == email))).scalars().all()
    assert len(users) == 1


@respx.mock
async def test_unmapped_group_defaults_to_host_never_admin(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, host_role: Role
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"unmapped-{uuid.uuid4().hex[:8]}@acme-test.example"

    response = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
        groups=["Some-Unmapped-Group"],
    )
    assert response.status_code == 307

    created_user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    role_names = {a.role.name for a in created_user.branch_roles}
    assert role_names == {"host"}
    assert "admin" not in role_names


async def test_login_initiate_without_configured_provider_returns_409(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.get(f"/api/v1/auth/sso/{tenant.slug}/login")
    assert response.status_code == 409


async def test_login_initiate_unknown_tenant_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/sso/no-such-tenant/login")
    assert response.status_code == 404


@respx.mock
async def test_callback_with_unrecognized_state_rejected(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id="cid", client_secret="s3cr3t"
    )
    _register_idp(urls, jwks=_jwks_document(private_key, "kid-1"), id_token="irrelevant")

    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": "not-a-real-state"}
    )
    assert response.status_code == 400


@respx.mock
async def test_callback_with_replayed_state_rejected(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, host_role: Role
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"replay-{uuid.uuid4().hex[:8]}@acme-test.example"

    _register_discovery_and_jwks(urls, jwks=_jwks_document(private_key, "kid-1"))
    initiate = await client.get(f"/api/v1/auth/sso/{tenant.slug}/login")
    location = httpx.URL(initiate.headers["location"])
    state = location.params["state"]
    nonce = location.params["nonce"]
    id_token = _sign_id_token(
        private_key,
        kid="kid-1",
        issuer=urls["issuer"],
        audience=client_id,
        nonce=nonce,
        email=email,
    )
    _register_token_endpoint(urls, id_token=id_token)

    first = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )
    assert first.status_code == 307

    second = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )
    assert second.status_code == 400


@respx.mock
async def test_callback_with_wrong_signature_rejected(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    urls = _idp_urls()
    signing_key = _rsa_keypair()
    other_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"tampered-{uuid.uuid4().hex[:8]}@acme-test.example"

    # Signed with `other_key`, but the JWKS served back only advertises
    # `signing_key`'s public half under the same kid — signature must fail.
    _register_discovery_and_jwks(urls, jwks=_jwks_document(signing_key, "kid-1"))
    initiate = await client.get(f"/api/v1/auth/sso/{tenant.slug}/login")
    location = httpx.URL(initiate.headers["location"])
    state = location.params["state"]
    nonce = location.params["nonce"]
    id_token = _sign_id_token(
        other_key, kid="kid-1", issuer=urls["issuer"], audience=client_id, nonce=nonce, email=email
    )
    _register_token_endpoint(urls, id_token=id_token)

    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )
    assert response.status_code == 400

    found = (await db_session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    assert found is None


@respx.mock
async def test_callback_with_expired_token_rejected(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"expired-{uuid.uuid4().hex[:8]}@acme-test.example"

    _register_discovery_and_jwks(urls, jwks=_jwks_document(private_key, "kid-1"))
    initiate = await client.get(f"/api/v1/auth/sso/{tenant.slug}/login")
    location = httpx.URL(initiate.headers["location"])
    state = location.params["state"]
    nonce = location.params["nonce"]
    id_token = _sign_id_token(
        private_key,
        kid="kid-1",
        issuer=urls["issuer"],
        audience=client_id,
        nonce=nonce,
        email=email,
        expires_in=-60,
    )
    _register_token_endpoint(urls, id_token=id_token)

    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )
    assert response.status_code == 400


@respx.mock
async def test_callback_writes_failure_audit_entry(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )

    _register_discovery_and_jwks(urls, jwks=_jwks_document(private_key, "kid-1"))
    initiate = await client.get(f"/api/v1/auth/sso/{tenant.slug}/login")
    location = httpx.URL(initiate.headers["location"])
    state = location.params["state"]
    nonce = location.params["nonce"]
    id_token = _sign_id_token(
        private_key,
        kid="kid-1",
        issuer=urls["issuer"],
        audience=client_id,
        nonce=nonce,
        email="whoever@acme-test.example",
        expires_in=-60,
    )
    _register_token_endpoint(urls, id_token=id_token)

    response = await client.get(
        "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": state}
    )
    assert response.status_code == 400

    failure_logs = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "sso_login_failed")))
        .scalars()
        .all()
    )
    assert len(failure_logs) == 1


@respx.mock
async def test_callback_rejects_existing_admin_account(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User
) -> None:
    """An existing Admin account must sign in via password login only —
    completing an otherwise-valid SSO callback for that email is rejected
    with the same generic error every other callback failure uses, but
    audited under its own action so the reason is still traceable
    server-side. See `openspec/changes/separate-admin-staff-login`.
    """
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )

    response = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=user.email,
    )
    assert response.status_code == 400

    audit_stmt = select(AuditLog.action).where(AuditLog.entity_id == user.id)
    audit_actions = (await db_session.execute(audit_stmt)).scalars().all()
    assert "sso_login_rejected_admin_account" in audit_actions
    assert "sso_login" not in audit_actions


# --- Exchange code: single-use, expiry ----------------------------------------


@respx.mock
async def test_exchange_code_cannot_be_reused(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, host_role: Role
) -> None:
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"once-{uuid.uuid4().hex[:8]}@acme-test.example"
    callback_response = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
    )
    exchange_code = httpx.URL(callback_response.headers["location"]).params["code"]

    first = await client.post("/api/v1/auth/sso/exchange", json={"code": exchange_code})
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/sso/exchange", json={"code": exchange_code})
    assert second.status_code == 401


@respx.mock
async def test_exchange_code_expires(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, host_role: Role, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "sso_exchange_code_ttl_seconds", 1)
    urls = _idp_urls()
    private_key = _rsa_keypair()
    client_id = "fake-client-id"
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id=client_id, client_secret="s3cr3t"
    )
    email = f"expiring-{uuid.uuid4().hex[:8]}@acme-test.example"
    callback_response = await _do_sso_login(
        client,
        tenant_slug=tenant.slug,
        urls=urls,
        private_key=private_key,
        kid="kid-1",
        client_id=client_id,
        email=email,
    )
    exchange_code = httpx.URL(callback_response.headers["location"]).params["code"]

    import asyncio

    await asyncio.sleep(1.5)

    response = await client.post("/api/v1/auth/sso/exchange", json={"code": exchange_code})
    assert response.status_code == 401


async def test_exchange_code_wrong_type_rejected(client: AsyncClient, user: User) -> None:
    """An ordinary access token is not a valid exchange code."""
    token = await _login(client, user.email)
    response = await client.post("/api/v1/auth/sso/exchange", json={"code": token})
    assert response.status_code == 401


async def test_exchange_code_too_long_rejected(client: AsyncClient) -> None:
    """`SsoExchangeRequest.code`'s `max_length=512` bound
    (`security-architecture.md` §4) — a real exchange code/JWT is well
    under this, so only a pathological payload should ever hit it.
    """
    response = await client.post("/api/v1/auth/sso/exchange", json={"code": "a" * 513})
    assert response.status_code == 422


# --- No lockout: password login unaffected by SSO -----------------------------


async def test_password_login_still_works_while_sso_enabled(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    urls = _idp_urls()
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id="cid", client_secret="s3cr3t"
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    assert response.status_code == 200


@respx.mock
async def test_password_login_unaffected_by_unreachable_idp(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    """Registers no IdP routes at all — if `POST /auth/login` ever called
    out to the IdP, respx would raise for the unmocked request.
    """
    urls = _idp_urls()
    await _save_provider(
        db_session, discovery_url=urls["discovery"], client_id="cid", client_secret="s3cr3t"
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    assert response.status_code == 200


# --- Rate limiting (design.md's "Rate limiting" decision) --------------------


async def test_login_initiate_rate_limit_trips(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [await client.get("/api/v1/auth/sso/no-such-tenant/login") for _ in range(10)]
    assert any(r.status_code == 429 for r in responses)


async def test_callback_rate_limit_trips(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.get(
            "/api/v1/auth/sso/callback", params={"code": "fake-code", "state": "bogus"}
        )
        for _ in range(10)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_exchange_rate_limit_trips(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.post("/api/v1/auth/sso/exchange", json={"code": "bogus"}) for _ in range(10)
    ]
    assert any(r.status_code == 429 for r in responses)


# --- Tenant isolation ----------------------------------------------------------


async def test_sso_provider_is_tenant_isolated(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession
) -> None:
    provider = await _save_provider(
        db_session,
        discovery_url="https://idp.example.com/.well-known/openid-configuration",
        client_id="cid",
        client_secret="s3cr3t",
    )

    other_schema = "tenant_other_sso_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        from vmss_api.sso.repository import SsoProviderRepository

        found = await SsoProviderRepository(other_session).get(provider.id)
        assert found is None


async def test_sso_role_mapping_is_tenant_isolated(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession, security_role: Role
) -> None:
    mapping = SsoRoleMappingFactory.build(
        id=uuid.uuid4(),
        idp_group_claim_value="VMS-Security-Team",
        role=security_role,
        deleted_at=None,
    )
    db_session.add(mapping)
    await db_session.commit()

    other_schema = "tenant_other_sso_role_mapping_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        from vmss_api.sso.repository import SsoRoleMappingRepository

        found = await SsoRoleMappingRepository(other_session).get(mapping.id)
        assert found is None
