import uuid
from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from factories import InvitationFactory, VisitorCategoryFactory
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import create_access_token, create_identity_verified_token
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """This feature's public endpoint has no `X-Device-Key`/bearer-tenant
    signal and resolves `settings.default_tenant_slug` the same way
    `identity-verification`/`registrations` already do — mirrors those
    features' own fixture of the same name.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


def _build_invitation(branch_id: uuid.UUID, **overrides) -> Invitation:
    """Builds (but does not add/commit) an `Invitation` row — same rationale
    as `invitations/tests.py::_build_invitation`: real FK-safe defaults for
    columns this feature never touches, one commit per test setup.
    """
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


def _proof_token(tenant: Tenant, identifier: str, channel: str = "email") -> str:
    return create_identity_verified_token(identifier, channel, tenant.id)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Token gating ------------------------------------------------------------


async def test_missing_proof_token_rejected(client: AsyncClient, tenant: Tenant) -> None:
    response = await client.get("/api/v1/visitor-portal/me")
    assert response.status_code == 401


async def test_wrong_token_type_rejected(client: AsyncClient, tenant: Tenant) -> None:
    """A staff access token must never be accepted in place of a
    verified-contact proof token (spec.md "A Non-Identity-Verification
    Token Is Rejected").
    """
    staff_token = create_access_token(uuid.uuid4(), tenant.id)
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(staff_token))
    assert response.status_code == 401


async def test_tampered_token_rejected(client: AsyncClient, tenant: Tenant) -> None:
    token = _proof_token(tenant, "visitor@example.com")
    response = await client.get(
        "/api/v1/visitor-portal/me", headers=_auth_headers(token + "tampered")
    )
    assert response.status_code == 401


async def test_valid_proof_token_is_accepted(client: AsyncClient, tenant: Tenant) -> None:
    token = _proof_token(tenant, "returning-visitor@example.com")
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200, response.text


# --- History and prefill -------------------------------------------------------


async def test_first_time_visitor_gets_empty_history_and_no_prefill(
    client: AsyncClient, tenant: Tenant
) -> None:
    """spec.md "No Prior Visit Found Returns an Empty Result, Not an Error"."""
    token = _proof_token(tenant, "first-timer@example.com")
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["history"] == []
    assert data["prefill"] is None


async def test_returning_visitor_sees_history_and_prefill_from_most_recent_visit(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    identifier = "jane@example.com"
    older_category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="Old Category", code="OLD-CAT"
    )
    newer_category = VisitorCategoryFactory.build(
        id=uuid.uuid4(), name="New Category", code="NEW-CAT"
    )
    db_session.add_all([older_category, newer_category])
    await db_session.commit()

    older = _build_invitation(
        branch.id,
        primary_contact_full_name="J Doe",
        primary_contact_email=identifier,
        primary_contact_phone=None,
        primary_contact_preferred_contact_method="email",
        primary_contact_id_proof_type="passport",
        primary_contact_id_proof_storage_key="docs/old-id.jpg",
        primary_contact_photo_storage_key=None,
        purpose_of_visit="Old meeting",
        preferred_visit_date=date.today() - timedelta(days=10),
        tracking_id="INV-OLDEST1",
        visitor_category_id=older_category.id,
    )
    newer = _build_invitation(
        branch.id,
        primary_contact_full_name="Jane Doe",
        primary_contact_email=identifier,
        primary_contact_phone=None,
        primary_contact_preferred_contact_method="email",
        primary_contact_id_proof_type="passport",
        primary_contact_id_proof_storage_key="docs/new-id.jpg",
        primary_contact_photo_storage_key=None,
        purpose_of_visit="New meeting",
        preferred_visit_date=date.today(),
        tracking_id="INV-NEWEST1",
        visitor_category_id=newer_category.id,
    )
    db_session.add_all([older, newer])
    await db_session.commit()
    # Force distinguishable `created_at` ordering: polyfactory assigns each
    # unset `Mapped[datetime]` field an independently random value (it has
    # no notion of `server_default`), spanning arbitrary years — backdating
    # only `older` relative to *itself* doesn't guarantee it sorts before
    # `newer`'s own random value, since `newer`'s random timestamp could
    # already be earlier. Pin both explicitly, relative to each other.
    now = datetime.now(UTC)
    newer.created_at = now
    older.created_at = now - timedelta(days=1)
    await db_session.commit()

    token = _proof_token(tenant, identifier)
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    tracking_ids = [entry["trackingId"] for entry in data["history"]]
    assert tracking_ids == ["INV-NEWEST1", "INV-OLDEST1"]

    prefill = data["prefill"]
    assert prefill["fullName"] == "Jane Doe"
    assert prefill["idProofType"] == "passport"
    # The newer visit's own ID-proof document, resolved to a fetchable URL —
    # the visitor's own OTP-proven identity is the access check here, not
    # `documents:view` (there is no staff caller on this endpoint).
    assert prefill["idProofUrl"] is not None
    # Drawn from the newer visit's category, not the older visit's.
    assert prefill["visitorCategoryId"] == str(newer_category.id)


async def test_prefill_missing_photo_and_id_proof_are_null_not_omitted(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    identifier = "no-photo@example.com"
    invitation = _build_invitation(
        branch.id,
        primary_contact_email=identifier,
        primary_contact_phone=None,
        primary_contact_photo_storage_key=None,
        primary_contact_id_proof_storage_key=None,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = _proof_token(tenant, identifier)
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200
    prefill = response.json()["data"]["prefill"]
    assert "photoUrl" in prefill
    assert prefill["photoUrl"] is None
    assert "idProofUrl" in prefill
    assert prefill["idProofUrl"] is None


async def test_prefill_missing_visitor_category_is_null_not_omitted(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    identifier = "no-category@example.com"
    invitation = _build_invitation(
        branch.id,
        primary_contact_email=identifier,
        primary_contact_phone=None,
        visitor_category_id=None,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = _proof_token(tenant, identifier)
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200
    prefill = response.json()["data"]["prefill"]
    assert "visitorCategoryId" in prefill
    assert prefill["visitorCategoryId"] is None


async def test_another_identifiers_visits_are_never_returned(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    other_identifier = "someone-else@example.com"
    invitation = _build_invitation(
        branch.id, primary_contact_email=other_identifier, primary_contact_phone=None
    )
    db_session.add(invitation)
    await db_session.commit()

    token = _proof_token(tenant, "verified-but-no-history@example.com")
    response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["history"] == []
    assert data["prefill"] is None


async def test_client_supplied_identifier_is_ignored(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "A client-supplied identifier in the request is ignored" —
    the endpoint takes no identifier param at all, so a caller has no field
    to smuggle a different identifier into; this asserts a query string
    value for an unrelated identifier has no effect.
    """
    proof_identifier = "verified@example.com"
    spoofed_identifier = "victim@example.com"
    victim_invitation = _build_invitation(
        branch.id, primary_contact_email=spoofed_identifier, primary_contact_phone=None
    )
    db_session.add(victim_invitation)
    await db_session.commit()

    token = _proof_token(tenant, proof_identifier)
    response = await client.get(
        "/api/v1/visitor-portal/me",
        params={"identifier": spoofed_identifier, "email": spoofed_identifier},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["data"]["history"] == []


# --- Default-tenant misconfiguration ------------------------------------------


async def test_unconfigured_default_tenant_logged_as_server_error(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "default_tenant_slug", "no-such-tenant-slug")
    token = _proof_token(tenant, "someone@example.com")

    with capture_logs() as captured:
        response = await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))

    assert response.status_code == 404
    [entry] = [
        e for e in captured if e["event"] == "visitor_return_visit_default_tenant_unconfigured"
    ]
    assert entry["log_level"] == "error"
    assert entry["reason"] == "not_found"


# --- Rate limiting -------------------------------------------------------------


async def test_returning_visitor_lookup_rate_limit_trips(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    monkeypatch.setattr(limiter, "enabled", True)
    token = _proof_token(tenant, "rate-limit-test@example.com")
    responses = [
        await client.get("/api/v1/visitor-portal/me", headers=_auth_headers(token))
        for _ in range(25)
    ]
    assert any(r.status_code == 429 for r in responses)


# --- No side effects on other capabilities -------------------------------------


async def test_walk_in_registration_and_invitation_endpoints_are_unaffected(
    client: AsyncClient,
) -> None:
    """design.md Decision 4 / proposal.md: this change is purely additive —
    a request to either existing public endpoint with no visitor-portal
    involvement at all must behave exactly as it did before this feature
    existed (rejected the same way, not a new/removed route).
    """
    response = await client.post("/api/v1/invitations", data={"payload": "{}"})
    assert response.status_code in (401, 422)

    response = await client.post("/api/v1/registrations/walk-in", data={"payload": "{}"})
    assert response.status_code in (401, 422)
