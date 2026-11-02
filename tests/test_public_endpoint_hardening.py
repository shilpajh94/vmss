"""public-endpoint-hardening spec: every covered endpoint keeps today's
anonymous contract (flagged `Deprecation: true`) while
`PUBLIC_ENDPOINT_HARDENING` is off, and enforces its credential once on."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import InvitationFactory, KioskFactory, UserFactory
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.security import create_identity_verified_token
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant


@pytest.fixture(autouse=True)
def _default_tenant_is_the_test_tenant(monkeypatch: pytest.MonkeyPatch, tenant: Tenant) -> None:
    """Anonymous calls resolve `settings.default_tenant_slug`."""
    monkeypatch.setattr(settings, "default_tenant_slug", tenant.slug)


@pytest.fixture
def strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "public_endpoint_hardening", True)


async def _employee(db_session: AsyncSession) -> None:
    db_session.add(
        UserFactory.build(
            id=uuid.uuid4(),
            email=f"staff-{uuid.uuid4().hex[:8]}@acme-test.example",
            phone_number="+91 90000 11122",
            employee_code=f"E-{uuid.uuid4().hex[:6]}",
        )
    )
    await db_session.commit()


# --- Employee listing ---------------------------------------------------------


async def test_anonymous_employee_list_is_unchanged_but_deprecated(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession
) -> None:
    await _employee(db_session)
    response = await client.get("/api/v1/auth/employees")
    assert response.status_code == 200, response.text
    assert response.headers["Deprecation"] == "true"
    assert "public-endpoint-hardening" in response.headers["Link"]
    assert all("email" in row for row in response.json()["data"])


async def test_anonymous_employee_list_drops_pii_in_strict_mode(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, strict: None
) -> None:
    await _employee(db_session)
    response = await client.get("/api/v1/auth/employees")
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert rows
    for row in rows:
        assert not {"email", "phoneNumber", "employeeCode", "branchRoles"} & set(row)
        assert {"id", "fullName"} <= set(row)


async def test_permitted_caller_gets_full_employee_fields_in_strict_mode(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], strict: None
) -> None:
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {issue_token(user)}"}
    )
    assert response.status_code == 200, response.text
    assert "Deprecation" not in response.headers
    assert all("email" in row for row in response.json()["data"])


# --- Kiosks -------------------------------------------------------------------


async def _kiosks(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            KioskFactory.build(id=uuid.uuid4(), name="Lobby"),
            KioskFactory.build(id=uuid.uuid4(), name="Back Office", is_hidden=True),
        ]
    )
    await db_session.commit()


async def test_anonymous_caller_cannot_reveal_hidden_kiosks(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession
) -> None:
    await _kiosks(db_session)
    response = await client.get("/api/v1/kiosks", params={"includeHidden": "true"})
    assert response.status_code == 200, response.text
    assert [k["name"] for k in response.json()["data"]] == ["Lobby"]
    assert response.headers["Deprecation"] == "true"


async def test_permitted_caller_still_sees_hidden_kiosks(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], db_session: AsyncSession
) -> None:
    await _kiosks(db_session)
    response = await client.get(
        "/api/v1/kiosks",
        params={"includeHidden": "true"},
        headers={"Authorization": f"Bearer {issue_token(user)}"},
    )
    assert response.status_code == 200, response.text
    assert sorted(k["name"] for k in response.json()["data"]) == ["Back Office", "Lobby"]


async def test_anonymous_kiosk_reads_require_auth_in_strict_mode(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, strict: None
) -> None:
    await _kiosks(db_session)
    assert (await client.get("/api/v1/kiosks")).status_code == 401


# --- Email tracking lookup ----------------------------------------------------


async def _invitation(db_session: AsyncSession, branch: Branch, **overrides) -> Invitation:
    fields = {
        "id": uuid.uuid4(),
        "branch_id": branch.id,
        "registration_type": "individual",
        "source": "staff_pre_registration",
        "primary_contact_email": "visitor@example.com",
        "created_by_user_id": None,
        "expires_at": datetime.now(UTC) + timedelta(hours=4),
        "preferred_visit_date": None,
    }
    fields.update(overrides)
    invitation = InvitationFactory.build(**fields)
    db_session.add(invitation)
    await db_session.commit()
    return invitation


async def test_email_tracking_is_deprecated_without_proof(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    await _invitation(db_session, branch)
    response = await client.get(
        "/api/v1/invitations/track", params={"email": "visitor@example.com"}
    )
    assert response.status_code == 200, response.text
    assert response.headers["Deprecation"] == "true"


async def test_email_tracking_requires_proof_in_strict_mode(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, strict: None
) -> None:
    await _invitation(db_session, branch)
    response = await client.get(
        "/api/v1/invitations/track", params={"email": "visitor@example.com"}
    )
    assert response.status_code == 401
    assert "trackingId" not in response.text


async def test_email_tracking_with_matching_proof_in_strict_mode(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, strict: None
) -> None:
    invitation = await _invitation(db_session, branch)
    tracking_id = invitation.tracking_id
    proof = create_identity_verified_token("visitor@example.com", "email", tenant.id)
    response = await client.get(
        "/api/v1/invitations/track",
        params={"email": "visitor@example.com"},
        headers={"Authorization": f"Bearer {proof}"},
    )
    assert response.status_code == 200, response.text
    assert "Deprecation" not in response.headers
    assert [row["trackingId"] for row in response.json()["data"]] == [tracking_id]


async def test_proof_for_another_email_does_not_count(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, strict: None
) -> None:
    await _invitation(db_session, branch)
    proof = create_identity_verified_token("someone-else@example.com", "email", tenant.id)
    response = await client.get(
        "/api/v1/invitations/track",
        params={"email": "visitor@example.com"},
        headers={"Authorization": f"Bearer {proof}"},
    )
    assert response.status_code == 401


# --- Tracking-ID check-in -----------------------------------------------------


async def _approved(db_session: AsyncSession, branch: Branch) -> Invitation:
    return await _invitation(
        db_session,
        branch,
        status="approved",
        check_in_status="unused",
        approved_at=datetime.now(UTC),
    )


async def test_anonymous_tracking_check_in_refused_in_strict_mode(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, strict: None
) -> None:
    invitation = await _approved(db_session, branch)
    invitation_id, tracking_id = invitation.id, invitation.tracking_id
    response = await client.patch(f"/api/v2/invitations/{tracking_id}/check-in")
    assert response.status_code == 401
    assert "primaryContact" not in response.text
    db_session.expire_all()
    refreshed = await db_session.get(Invitation, invitation_id)
    assert refreshed is not None and refreshed.status == "approved"


async def test_staff_with_checkin_permission_checks_in_in_strict_mode(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    user: User,
    issue_token: Callable[[User], str],
    db_session: AsyncSession,
    strict: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vmss_api.notifications import service as notifications_service

    async def _noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(notifications_service, "notify_user", _noop)
    token = issue_token(user)
    invitation = await _approved(db_session, branch)
    response = await client.patch(
        f"/api/v2/invitations/{invitation.tracking_id}/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert "Deprecation" not in response.headers
