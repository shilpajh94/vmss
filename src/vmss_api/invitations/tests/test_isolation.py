"""Tenant isolation for every invitation repository path."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.invitations.repository import InvitationRepository
from vmss_api.invitations.tests.helpers import (
    _branch_scoped_invitation_approver,
    _build_invitation,
    _create_invitation_success,
    _group_payload,
    _individual_payload,
    _login,
)
from vmss_api.org_structure.models import Branch
from vmss_api.tenant.models import Tenant

# --- Tenant isolation ---------------------------------------------------------


@pytest.mark.parametrize(
    ("payload_factory", "visitor_file_count"),
    [(_individual_payload, 0), (_group_payload, 2)],
    ids=["individual", "group"],
)
async def test_invitation_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    user: User,
    branch: Branch,
    client: AsyncClient,
    payload_factory,
    visitor_file_count: int,
) -> None:
    token = await _login(client, user.email)
    data = await _create_invitation_success(
        client, token, branch, payload=payload_factory(), visitor_file_count=visitor_file_count
    )

    other_schema = "tenant_other_test_invitations"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).get_by_tracking_id(data["trackingId"])
        assert found is None


# --- Tenant isolation ------------------------------------------------------------


async def test_check_in_repository_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_checkin"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).check_in_if_eligible(
            invitation.id, user_id=uuid.uuid4()
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_approve_if_submitted_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted", approved_at=None)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_approve"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).approve_if_submitted(invitation.id)
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"
    assert invitation.approved_at is None


async def test_deny_if_submitted_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_deny"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).deny_if_submitted(
            invitation.id, reason="Not on the expected list"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_check_out_if_checked_in_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=datetime.now(UTC),
        checked_in_at=datetime.now(UTC),
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_checkout"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).check_out_if_checked_in(
            invitation.id, user_id=uuid.uuid4()
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"


async def test_reschedule_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()
    original_date = invitation.preferred_visit_date

    other_schema = "tenant_other_test_invitation_reschedule"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).reschedule_if_eligible(
            invitation.id,
            preferred_visit_date=date(2026, 12, 1),
            preferred_visit_time=time(15, 30),
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.preferred_visit_date == original_date


async def test_extend_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    original_expiry = now + timedelta(days=1)
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=now, expires_at=original_expiry
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_extend"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).extend_if_eligible(
            invitation.id, new_expires_at=now + timedelta(days=7)
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.expires_at == original_expiry


async def test_issue_badge_if_eligible_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_badge_issue"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).issue_badge_if_eligible(
            invitation.id, badge_number="BDG-DEADBEEF", badge_storage_key="badges/other.png"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.badge_number is None


async def test_reprint_badge_if_issued_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        badge_number="BDG-11112222",
        badge_storage_key="badges/original.png",
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_badge_reprint"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).reprint_badge_if_issued(
            invitation.id, badge_storage_key="badges/other-reprint.png"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.badge_storage_key == "badges/original.png"
    assert invitation.badge_reprint_count == 0


async def test_override_watchlist_if_flagged_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=datetime.now(UTC),
        watchlist_flagged=True,
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_watchlist_override"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        updated = await InvitationRepository(other_session).override_watchlist_if_flagged(
            invitation.id, user_id=uuid.uuid4(), reason="Confirmed false positive"
        )
        assert updated is None

    await db_session.refresh(invitation)
    assert invitation.watchlist_flagged is True


async def test_list_by_primary_contact_email_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """Covers the email-lookup path of `GET /invitations/track` — the
    trackingId path is already covered by
    `test_invitation_repository_tenant_schema_isolation` above.
    """
    email = f"tracked-{uuid.uuid4().hex[:8]}@example.com"
    invitation = _build_invitation(db_session, branch.id, primary_contact_email=email)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_track_by_email"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).list_by_primary_contact_email(email)
        assert found == []


async def test_get_with_children_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """Covers `GET /invitations/{id}`'s own repository method."""
    invitation = _build_invitation(db_session, branch.id, status="approved")
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_get_with_children"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await InvitationRepository(other_session).get_with_children(invitation.id)
        assert found is None


async def test_get_invitation_detail_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """testing-standards.md §2 permission-denied case, distinct from
    `test_get_invitation_detail_denied_for_viewer_scoped_elsewhere` above:
    that test's caller has zero access to the invitation's own branch at
    all, which trips `authorize_branch_id_tolerant`'s *first* guard ("No
    access to this branch"). This caller is correctly scoped to the
    invitation's own branch (a real `invitations:approve` grant there) but
    holds no `invitations:view` permission at all — the *second* guard
    ("Insufficient permission"), the "no permission whatsoever" 403 branch
    task 3.4 asks for.
    """
    caller = await _branch_scoped_invitation_approver(db_session, tenant, branch.id)
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(caller)
    response = await client.get(
        f"/api/v1/invitations/{invitation.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
