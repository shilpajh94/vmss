"""serve-email-images-by-url-and-complete-contact: the signed QR URL
helpers (`core/email_assets.py`) and the public email-asset routes.
"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import InvitationFactory, TenantFactory
from vmss_api.auth.models import User
from vmss_api.core import email_assets
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.invitations.models import InvitationQRCode
from vmss_api.invitations.qr import generate_qr_png
from vmss_api.main import app
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

_BASE = "https://api.example.test"


@pytest.fixture
def _base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", _BASE)


def _split(url: str) -> tuple[str, int, str]:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    return parts.path, int(query["exp"][0]), query["sig"][0]


# --- signing ------------------------------------------------------------------


def test_logo_url_is_absolute_under_the_base(_base_url) -> None:
    assert email_assets.logo_url() == f"{_BASE}/api/v1/public/email-assets/visimio-logo.png"


def test_urls_are_none_without_a_base(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", None)
    assert email_assets.logo_url() is None
    assert email_assets.sign_qr_url(uuid.uuid4(), uuid.uuid4(), datetime.now(UTC)) is None


def test_trailing_slash_on_base_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_asset_base_url", f"{_BASE}/")
    assert email_assets.logo_url() == f"{_BASE}/api/v1/public/email-assets/visimio-logo.png"


def test_signed_qr_url_verifies_and_expires_seven_days_after_the_visit(_base_url) -> None:
    tenant_id, invitation_id = uuid.uuid4(), uuid.uuid4()
    visit_expires_at = datetime(2026, 10, 14, 18, 0, tzinfo=UTC)

    url = email_assets.sign_qr_url(tenant_id, invitation_id, visit_expires_at)

    assert url is not None
    path, exp, sig = _split(url)
    assert path == f"/api/v1/public/email-assets/{tenant_id}/qr/{invitation_id}.png"
    assert exp == int((visit_expires_at + timedelta(days=7)).timestamp())
    assert email_assets.verify_qr_signature(tenant_id, invitation_id, exp, sig)


@pytest.mark.parametrize("field", ["tenant", "invitation", "exp", "sig"])
def test_tampering_with_any_field_fails_verification(_base_url, field: str) -> None:
    tenant_id, invitation_id = uuid.uuid4(), uuid.uuid4()
    url = email_assets.sign_qr_url(tenant_id, invitation_id, datetime.now(UTC))
    assert url is not None
    _, exp, sig = _split(url)
    if field == "tenant":
        tenant_id = uuid.uuid4()
    elif field == "invitation":
        invitation_id = uuid.uuid4()
    elif field == "exp":
        exp += 1
    else:
        sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    assert not email_assets.verify_qr_signature(tenant_id, invitation_id, exp, sig)


def test_expiry_check() -> None:
    now = int(time.time())
    assert email_assets.is_expired(now - 1)
    assert not email_assets.is_expired(now + 60)


# --- routes -------------------------------------------------------------------


async def _approved_invitation_with_qr(
    db_session: AsyncSession, branch: Branch, creator: User, *, expires_at: datetime
) -> tuple[uuid.UUID, str]:
    invitation = InvitationFactory.build(
        id=uuid.uuid4(),
        branch_id=branch.id,
        created_by_user_id=creator.id,
        status="approved",
        expires_at=expires_at,
    )
    token = f"persisted-token-{uuid.uuid4().hex}"
    db_session.add(invitation)
    await db_session.flush()
    db_session.add(
        InvitationQRCode(
            id=uuid.uuid4(), invitation_id=invitation.id, qr_token=token, image_storage_key="k"
        )
    )
    await db_session.commit()
    return invitation.id, token


def _relative(url: str | None) -> str:
    assert url is not None
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


async def test_logo_route_serves_png_with_immutable_caching(client: AsyncClient) -> None:
    response = await client.get("/api/v1/public/email-assets/visimio-logo.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert "immutable" in response.headers["cache-control"]


async def test_qr_route_serves_the_persisted_token_png(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=1)
    invitation_id, token = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )
    url = email_assets.sign_qr_url(tenant.id, invitation_id, expires_at)

    response = await client.get(_relative(url))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=86400"
    # `generate_qr_png` is deterministic, so identical bytes mean the image
    # encodes exactly the persisted token.
    assert response.content == await generate_qr_png(token)
    assert token.encode() not in response.content


async def test_qr_route_rejects_a_swapped_invitation_id(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=1)
    first_id, _ = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )
    second_id, _ = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )
    url = _relative(email_assets.sign_qr_url(tenant.id, first_id, expires_at))

    response = await client.get(url.replace(str(first_id), str(second_id)))

    assert response.status_code == 403
    assert not response.headers["content-type"].startswith("image/")


async def test_qr_route_rejects_a_swapped_tenant_id(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=1)
    invitation_id, _ = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )
    url = _relative(email_assets.sign_qr_url(tenant.id, invitation_id, expires_at))

    response = await client.get(url.replace(str(tenant.id), str(uuid.uuid4())))

    assert response.status_code == 403


async def test_qr_route_returns_410_once_expired(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    # Visit window closed 8 days ago, so the 7-day grace has passed too.
    expires_at = datetime.now(UTC) - timedelta(days=8)
    invitation_id, _ = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )

    response = await client.get(
        _relative(email_assets.sign_qr_url(tenant.id, invitation_id, expires_at))
    )

    assert response.status_code == 410


async def test_qr_route_returns_404_for_an_unknown_tenant(
    _base_url, client: AsyncClient, tenant: Tenant
) -> None:
    url = email_assets.sign_qr_url(uuid.uuid4(), uuid.uuid4(), datetime.now(UTC) + timedelta(1))

    response = await client.get(_relative(url))

    assert response.status_code == 404


async def test_qr_route_returns_404_for_an_unknown_invitation(
    _base_url, client: AsyncClient, tenant: Tenant
) -> None:
    url = email_assets.sign_qr_url(tenant.id, uuid.uuid4(), datetime.now(UTC) + timedelta(1))

    response = await client.get(_relative(url))

    assert response.status_code == 404


async def test_qr_route_returns_404_when_no_qr_was_issued(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=1)
    invitation = InvitationFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, created_by_user_id=user.id, expires_at=expires_at
    )
    db_session.add(invitation)
    await db_session.commit()

    response = await client.get(
        _relative(email_assets.sign_qr_url(tenant.id, invitation.id, expires_at))
    )

    assert response.status_code == 404


async def test_qr_route_does_not_serve_another_tenants_invitation(
    _base_url,
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    user: User,
    make_tenant_schema,
) -> None:
    """Tenant isolation: a validly signed URL naming tenant B can't reach an
    invitation that only exists in tenant A's schema."""
    other_schema = "tenant_email_assets_other"
    await make_tenant_schema(other_schema)
    other = TenantFactory.build(
        id=uuid.uuid4(), slug="email-assets-other", schema_name=other_schema, timezone="UTC"
    )
    db_session.add(other)
    await db_session.commit()
    expires_at = datetime.now(UTC) + timedelta(days=1)
    invitation_id, _ = await _approved_invitation_with_qr(
        db_session, branch, user, expires_at=expires_at
    )

    response = await client.get(
        _relative(email_assets.sign_qr_url(other.id, invitation_id, expires_at))
    )

    assert response.status_code == 404


async def test_qr_route_is_rate_limited(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    url = f"/api/v1/public/email-assets/{uuid.uuid4()}/qr/{uuid.uuid4()}.png?exp=1&sig=x"

    statuses = [(await client.get(url)).status_code for _ in range(65)]

    assert 429 in statuses


def test_email_asset_routes_are_documented_under_their_tag() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    for path in (
        "/api/v1/public/email-assets/visimio-logo.png",
        "/api/v1/public/email-assets/{tenant_id}/qr/{invitation_id}.png",
    ):
        assert paths[path]["get"]["tags"] == ["email-assets"]
    tags = {tag["name"]: tag.get("description") for tag in schema.get("tags", [])}
    assert tags.get("email-assets")
