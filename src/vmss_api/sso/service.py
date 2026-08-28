import json
import secrets
import uuid

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth import service as auth_service
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import Role, User
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.auth.schemas import TokenResponse
from vmss_api.core import encryption
from vmss_api.core.config import settings
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.redis import get_redis
from vmss_api.core.security import (
    create_access_token,
    create_refresh_token,
    create_sso_exchange_token,
    decode_token,
    hash_password,
)
from vmss_api.sso import oidc_client
from vmss_api.sso.models import SsoProvider, SsoRoleMapping
from vmss_api.sso.repository import SsoProviderRepository, SsoRoleMappingRepository
from vmss_api.sso.schemas import (
    SsoProviderConfigIn,
    SsoProviderTestRequest,
    SsoProviderTestResult,
    SsoRoleMappingIn,
)
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_HOST_DEFAULT_ROLE_NAME = "host"


def _state_key(state: str) -> str:
    """Deliberately NOT tenant-prefixed — the callback that looks this key
    up doesn't know the tenant yet; resolving it is the point of this
    record. `state` is itself a 256-bit random token, so no tenant segment
    is needed for isolation. See design.md's "`state`/exchange Redis keys
    are NOT tenant-prefixed" decision.
    """
    return f"vmss:sso:state:{state}"


def _exchange_key(jti: str) -> str:
    return f"vmss:sso:exchange:{jti}"


# --- Admin configuration -------------------------------------------------


async def save_provider_config(
    tenant_db: AsyncSession, payload: SsoProviderConfigIn
) -> SsoProvider:
    repo = SsoProviderRepository(tenant_db)
    existing = await repo.get_any()
    encrypted_secret = encryption.encrypt(payload.client_secret)
    masked_secret = encryption.mask_secret(payload.client_secret)

    if existing is None:
        provider = SsoProvider(
            id=uuid.uuid4(),
            display_name=payload.display_name,
            discovery_url=payload.discovery_url,
            client_id=payload.client_id,
            client_secret_encrypted=encrypted_secret,
            client_secret_masked=masked_secret,
            is_enabled=payload.is_enabled,
        )
        tenant_db.add(provider)
    else:
        provider = existing
        provider.display_name = payload.display_name
        provider.discovery_url = payload.discovery_url
        provider.client_id = payload.client_id
        provider.client_secret_encrypted = encrypted_secret
        provider.client_secret_masked = masked_secret
        provider.is_enabled = payload.is_enabled

    await tenant_db.commit()
    await tenant_db.refresh(provider)
    return provider


async def get_provider_config(tenant_db: AsyncSession) -> SsoProvider | None:
    return await SsoProviderRepository(tenant_db).get_any()


async def test_provider_config(payload: SsoProviderTestRequest) -> SsoProviderTestResult:
    """Validates a candidate configuration against the live IdP without
    persisting anything — spec.md's "Provider Connection Can Be Tested
    Before Saving" requirement.
    """
    try:
        await oidc_client.test_client_credentials(
            payload.discovery_url,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
        )
    except (
        oidc_client.OidcDiscoveryError,
        oidc_client.OidcConfigTestError,
        oidc_client.UnsafeDiscoveryUrlError,
    ) as exc:
        return SsoProviderTestResult(success=False, message=str(exc))
    return SsoProviderTestResult(success=True, message="Connection test succeeded")


async def list_role_mappings(tenant_db: AsyncSession) -> list[SsoRoleMapping]:
    return await SsoRoleMappingRepository(tenant_db).list_all()


async def create_role_mapping(tenant_db: AsyncSession, payload: SsoRoleMappingIn) -> SsoRoleMapping:
    role_repo = RoleRepository(tenant_db)
    role = await role_repo.get(payload.role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.name == "visitor":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="The visitor role cannot be granted via SSO"
        )
    if role.name == "admin":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="The admin role cannot be granted via SSO"
        )

    mapping_repo = SsoRoleMappingRepository(tenant_db)
    if await mapping_repo.get_by_group_claim_value(payload.idp_group_claim_value) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="This IdP group is already mapped to a role"
        )

    mapping = SsoRoleMapping(
        id=uuid.uuid4(), idp_group_claim_value=payload.idp_group_claim_value, role_id=role.id
    )
    mapping.role = role
    tenant_db.add(mapping)
    await tenant_db.commit()
    return mapping


async def delete_role_mapping(tenant_db: AsyncSession, mapping_id: uuid.UUID) -> None:
    repo = SsoRoleMappingRepository(tenant_db)
    mapping = await repo.get(mapping_id)
    if mapping is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role mapping not found")
    await repo.delete(mapping)
    await tenant_db.commit()


# --- Login flow ------------------------------------------------------------


class SsoNotConfiguredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, detail="SSO is not configured for this tenant")


class InvalidSsoCallbackError(HTTPException):
    def __init__(self, detail: str = "SSO login could not be verified") -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail=detail)


async def _require_tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant:
    tenant = await TenantRepository(db).get_by_slug(tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


async def start_login(db: AsyncSession, tenant_slug: str) -> str:
    """Resolves `tenant_slug` (a public, non-secret identifier — see
    design.md's "Tenant resolution for the public initiate endpoint"
    decision) to the tenant's enabled provider and returns the authorization
    URL to redirect the browser to.
    """
    tenant = await _require_tenant_by_slug(db, tenant_slug)
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        provider = await SsoProviderRepository(tenant_db).get_enabled()
    if provider is None:
        raise SsoNotConfiguredError()

    if not settings.sso_redirect_uri:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="SSO redirect URI is not configured"
        )

    try:
        discovery = await oidc_client.fetch_discovery_document(provider.discovery_url)
    except (oidc_client.OidcDiscoveryError, oidc_client.UnsafeDiscoveryUrlError) as exc:
        logger.warning("sso_login_initiate_failed", tenant_id=str(tenant.id), reason=str(exc))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="SSO provider is currently unreachable"
        ) from exc
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    redis = await get_redis()
    record = json.dumps({"tenant_id": str(tenant.id), "nonce": nonce})
    await redis.set(_state_key(state), record, ex=settings.sso_state_ttl_seconds)

    return oidc_client.build_authorization_url(
        discovery,
        client_id=provider.client_id,
        redirect_uri=settings.sso_redirect_uri,
        state=state,
        nonce=nonce,
    )


async def handle_callback(
    db: AsyncSession, *, code: str, state: str, background_tasks: BackgroundTasks
) -> str:
    """Verifies the callback (state, then the ID token itself), resolves or
    JIT-provisions the account, audits the outcome, and returns a
    short-lived exchange code for the browser to redeem — never the real
    token pair directly. See spec.md's "The Callback Verifies the ID Token
    Before Trusting Any Claim" and "Tokens Are Handed to the Caller Through
    a Short-Lived, Single-Use Exchange" requirements.
    """
    redis = await get_redis()
    raw_record = await redis.getdel(_state_key(state))
    if raw_record is None:
        raise InvalidSsoCallbackError("Login attempt not found or already used")
    record = json.loads(raw_record)
    tenant_id = uuid.UUID(record["tenant_id"])
    nonce = record["nonce"]

    tenant = await TenantRepository(db).get(tenant_id)
    if tenant is None or not tenant.is_active:
        raise InvalidSsoCallbackError()

    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        provider = await SsoProviderRepository(tenant_db).get_enabled()
        if provider is None:
            raise InvalidSsoCallbackError("SSO is no longer enabled for this tenant")

        try:
            discovery = await oidc_client.fetch_discovery_document(provider.discovery_url)
            token_response = await oidc_client.exchange_code_for_tokens(
                discovery,
                code=code,
                client_id=provider.client_id,
                client_secret=encryption.decrypt(provider.client_secret_encrypted),
                redirect_uri=settings.sso_redirect_uri or "",
            )
            id_token = token_response["id_token"]
            claims = oidc_client.verify_id_token(
                id_token,
                jwks_uri=discovery.jwks_uri,
                issuer=discovery.issuer,
                audience=provider.client_id,
                nonce=nonce,
            )
        except (
            oidc_client.OidcDiscoveryError,
            oidc_client.OidcTokenExchangeError,
            oidc_client.InvalidIdTokenError,
            oidc_client.UnsafeDiscoveryUrlError,
            KeyError,
        ) as exc:
            logger.warning("sso_login_failed", tenant_id=str(tenant.id), reason=type(exc).__name__)
            # Written synchronously, NOT via `background_tasks.add_task` —
            # a route that raises an `HTTPException` never gets its
            # `BackgroundTasks` attached to the error response
            # `core/middleware.py::http_exception_handler` builds instead
            # (FastAPI only wires `.background` onto the endpoint's own
            # returned response), so a background-scheduled audit write
            # here would silently never run. See design.md.
            await record_audit_log(
                tenant.schema_name,
                actor_user_id=None,
                action="sso_login_failed",
                entity_type="User",
                entity_id=None,
            )
            raise InvalidSsoCallbackError() from None

        email = claims.get("email") or claims.get("preferred_username")
        if not email:
            logger.warning(
                "sso_login_failed", tenant_id=str(tenant.id), reason="missing_email_claim"
            )
            await record_audit_log(
                tenant.schema_name,
                actor_user_id=None,
                action="sso_login_failed",
                entity_type="User",
                entity_id=None,
            )
            raise InvalidSsoCallbackError("ID token did not include an email claim")

        full_name = claims.get("name") or email
        groups = claims.get("groups") or []

        user, created = await _provision_or_resolve_user(
            tenant_db, tenant_id=tenant.id, email=email, full_name=full_name, groups=groups
        )

        if not created and auth_service.has_admin_role(user):
            # Admin signs in via password login only (`auth` capability) —
            # an existing Admin account can never complete SSO, even though
            # a brand-new JIT-provisioned account already can't default to
            # Admin (see `create_role_mapping`'s guard). Rejected with the
            # same generic error every other callback failure uses, so an
            # unauthenticated caller can't use this endpoint to learn
            # whether an email belongs to an Admin account — but recorded
            # under its own audit action, not the generic
            # `sso_login_failed`, so the reason is still traceable
            # server-side. Written synchronously, not via
            # `background_tasks.add_task`, for the same reason every other
            # rejection above in this function is: a raised
            # `HTTPException`'s response never gets `BackgroundTasks`
            # attached.
            logger.warning(
                "sso_login_rejected_admin_account", tenant_id=str(tenant.id), user_id=str(user.id)
            )
            await record_audit_log(
                tenant.schema_name,
                actor_user_id=user.id,
                action="sso_login_rejected_admin_account",
                entity_type="User",
                entity_id=user.id,
            )
            raise InvalidSsoCallbackError()

    if created:
        background_tasks.add_task(
            record_audit_log,
            tenant.schema_name,
            actor_user_id=user.id,
            action="sso_account_created",
            entity_type="User",
            entity_id=user.id,
        )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="sso_login",
        entity_type="User",
        entity_id=user.id,
    )

    return create_sso_exchange_token(user.id, tenant.id)


async def _provision_or_resolve_user(
    tenant_db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    full_name: str,
    groups: list[str],
) -> tuple[User, bool]:
    """JIT provisioning — spec.md's "Just-in-Time Provisioning Resolves to
    Exactly One Account Per Email" requirement. Role assignment only ever
    comes from `SsoRoleMapping` (Admin-curated), never a raw claim value
    interpreted as a role name — design.md's "Role assignment only ever
    comes from the curated mapping table" decision.
    """
    existing = await UserRepository(tenant_db).get_by_email(email)
    if existing is not None:
        return existing, False

    role_repo = RoleRepository(tenant_db)
    mapping = await SsoRoleMappingRepository(tenant_db).get_first_match(groups)
    role: Role | None
    if mapping is not None:
        role = mapping.role
    else:
        role = await role_repo.get_by_name(_HOST_DEFAULT_ROLE_NAME)

    user = await auth_service.create_user(
        tenant_db,
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        full_name=full_name,
        role_assignments=[(role, None)] if role is not None else None,
    )
    await tenant_db.commit()
    return user, True


# --- Token exchange ----------------------------------------------------------


async def redeem_exchange_code(code: str) -> TokenResponse:
    """Redeems a short-lived, single-use exchange code for the real
    access/refresh token pair — spec.md's "Tokens Are Handed to the Caller
    Through a Short-Lived, Single-Use Exchange" requirement. No database
    access is needed: the exchange token's claims carry everything
    `create_access_token`/`create_refresh_token` need, and every subsequent
    request re-validates the user via `get_current_user` regardless of how
    the token pair was obtained.
    """
    claims = decode_token(code)
    if claims.get("type") != "sso_exchange":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not a valid SSO exchange code")

    tenant_id = uuid.UUID(claims["tenant_id"])
    user_id = uuid.UUID(claims["sub"])
    jti = claims["jti"]

    redis = await get_redis()
    claimed = await redis.set(
        _exchange_key(jti), "1", nx=True, ex=settings.sso_exchange_code_ttl_seconds
    )
    if not claimed:
        logger.warning("sso_exchange_replay_rejected", tenant_id=str(tenant_id))
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="SSO exchange code already used or expired"
        )

    return TokenResponse(
        access_token=create_access_token(user_id, tenant_id),
        refresh_token=create_refresh_token(user_id, tenant_id),
    )
