"""GET /invitations: listing, sorting and the relevantToMe filter."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BranchFactory,
    CompanyFactory,
    InvitationFactory,
    RoleFactory,
    UserFactory,
)
from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.approvals.repository import InvitationApprovalStepRepository
from vmss_api.auth.models import User
from vmss_api.auth.repository import RoleRepository
from vmss_api.core import storage
from vmss_api.core.schemas import SortOrder
from vmss_api.invitations import service as invitations_service
from vmss_api.invitations.repository import InvitationRepository, VisitDayRange
from vmss_api.invitations.tests.helpers import (
    _KOLKATA,
    _branch_scoped_invitation_viewer,
    _build_invitation,
    _build_status_row,
    _csv_rows,
    _delegate_step,
    _invitation_with_host_step,
    _invitation_with_role_step,
    _jpeg_bytes,
    _list_rows,
    _login,
    _make_role_holder,
    _submitted_with_steps,
)
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant

# --- Employee listing (GET /invitations) -------------------------------------


async def test_list_invitations_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    tracking_ids = {row["trackingId"] for row in body["data"]}
    assert invitation.tracking_id in tracking_ids
    row = next(r for r in body["data"] if r["trackingId"] == invitation.tracking_id)
    assert set(row.keys()) == {
        "id",
        "trackingId",
        "registrationType",
        "source",
        "status",
        "visitorCategoryId",
        "primaryContactFullName",
        "primaryContactEmail",
        "primaryContactPhone",
        "primaryContactPhotoUrl",
        "purposeOfVisit",
        "departmentToVisit",
        "departmentId",
        "buildingId",
        "expiresAt",
        "submittedAt",
        "approvedAt",
        "archivedAt",
        "checkedOutAutomatically",
        "statusChangedAt",
        "preferredVisitDate",
        "preferredVisitTime",
        "currentApprovalStep",
    }
    assert row["visitorCategoryId"] is None
    assert row["primaryContactPhotoUrl"] is None
    assert row["primaryContactEmail"] == invitation.primary_contact_email
    assert row["primaryContactPhone"] == invitation.primary_contact_phone


async def test_list_invitations_surfaces_schedule_and_current_step(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """invitations delta "Invitation List Items Surface the Preferred Visit
    Date and Time": level 2 of 3 pending shows in the list item itself."""
    invitation = await _submitted_with_steps(db_session, branch.id, user, pending_from=1)
    tracking_id = invitation.tracking_id
    token = await _login(client, user.email)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()["data"] if r["trackingId"] == tracking_id)
    assert row["preferredVisitDate"] == "2026-11-03"
    assert row["preferredVisitTime"] == "09:30:00"
    assert row["currentApprovalStep"]["stepOrder"] == 1
    assert row["currentApprovalStep"]["totalSteps"] == 3


async def test_list_invitations_query_count_does_not_grow_with_page_size(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """query-performance.md §2: the current-step lookup is one batch query
    per page, never one per row."""
    from sqlalchemy import event

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    engine = db_session.bind.sync_engine  # type: ignore[union-attr]

    async def _count_list_queries() -> int:
        statements: list[str] = []

        def _record(conn, cursor, statement, *args) -> None:
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _record)
        try:
            response = await client.get("/api/v1/invitations", headers=headers)
        finally:
            event.remove(engine, "before_cursor_execute", _record)
        assert response.status_code == 200, response.text
        return len(statements)

    await _submitted_with_steps(db_session, branch.id, user, pending_from=0)
    one = await _count_list_queries()
    for _ in range(3):
        await _submitted_with_steps(db_session, branch.id, user, pending_from=0)
    four = await _count_list_queries()
    assert four == one


async def test_list_invitations_surfaces_primary_contact_photo_url(
    client: AsyncClient, user: User, branch: Branch, tenant: Tenant, db_session: AsyncSession
) -> None:
    """qr-checkin-scheduling-photo-email spec.md "List row surfaces the
    primary contact's photo URL when one was captured" — matches what the
    tracking/detail endpoints already return for the same invitation.

    add-avatar-upload-and-verify-image-storage spec.md "Every photo URL
    returned by any invitation response ... SHALL be a fetchable HTTP URL"
    — asserts the list row's URL is genuinely fetchable, not just non-null.
    """
    photo_bytes = _jpeg_bytes()
    photo_key = await storage.save(tenant.id, "invitations/photos", photo_bytes, "image/jpeg")
    invitation = _build_invitation(
        db_session,
        branch.id,
        primary_contact_photo_storage_key=photo_key,
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["trackingId"] == invitation.tracking_id)
    assert row["primaryContactPhotoUrl"] is not None

    photo_response = await client.get(row["primaryContactPhotoUrl"])
    assert photo_response.status_code == 200
    assert photo_response.content == photo_bytes


async def test_list_invitations_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_list_invitations_branch_header_narrows_to_one_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV")
    db_session.add(other_branch)
    await db_session.flush()

    in_scope = _build_invitation(db_session, branch.id)
    other_branch_invitation = _build_invitation(db_session, other_branch.id)
    db_session.add_all([in_scope, other_branch_invitation])
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert in_scope.tracking_id in tracking_ids
    assert other_branch_invitation.tracking_id not in tracking_ids


async def test_list_invitations_unauthorized_branch_id_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV-2")
    db_session.add(other_branch)
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(other_branch.id)},
    )
    assert response.status_code == 403


async def test_list_invitations_without_branch_header_returns_every_authorized_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-INV-3")
    db_session.add(other_branch)
    await db_session.flush()

    invitation = _build_invitation(db_session, branch.id)
    other_branch_invitation = _build_invitation(db_session, other_branch.id)
    db_session.add_all([invitation, other_branch_invitation])
    await db_session.commit()

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get("/api/v1/invitations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids
    assert other_branch_invitation.tracking_id not in tracking_ids


# --- sort-invitation-board-by-status-date -------------------------------------


async def test_list_invitations_status_changed_at_orders_checked_in_by_check_in_time(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Checked-in column orders by most recent check-in"."""
    marker = f"chk{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    recent_check_in = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_in",
        submitted_at=now - timedelta(days=3),
        checked_in_at=now - timedelta(minutes=5),
    )
    older_check_in = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_in",
        submitted_at=now - timedelta(days=1),
        checked_in_at=now - timedelta(hours=2),
    )
    db_session.add_all([recent_check_in, older_check_in])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, status="checked_in", sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        recent_check_in.tracking_id,
        older_check_in.tracking_id,
    ]
    assert datetime.fromisoformat(rows[0]["statusChangedAt"]) == recent_check_in.checked_in_at

    default_rows = await _list_rows(client, token, marker, status="checked_in")
    assert [row["trackingId"] for row in default_rows] == [
        older_check_in.tracking_id,
        recent_check_in.tracking_id,
    ]


@pytest.mark.parametrize(
    ("status", "timestamp_field"),
    [
        ("approved", "approved_at"),
        ("checked_out", "checked_out_at"),
        ("denied", "denied_at"),
        ("archived", "archived_at"),
    ],
)
async def test_list_invitations_status_changed_at_uses_each_status_timestamp(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    status: str,
    timestamp_field: str,
) -> None:
    """spec.md "Each status column orders by its own status time" and
    "Ascending order is supported" — the older-submitted row changed status
    most recently, so it leads under `desc` and trails under `asc`."""
    marker = f"st{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    changed_recently = _build_status_row(
        db_session,
        branch.id,
        marker,
        status,
        submitted_at=now - timedelta(days=5),
        **{timestamp_field: now - timedelta(minutes=1)},
    )
    changed_earlier = _build_status_row(
        db_session,
        branch.id,
        marker,
        status,
        submitted_at=now - timedelta(days=1),
        **{timestamp_field: now - timedelta(hours=6)},
    )
    db_session.add_all([changed_recently, changed_earlier])
    await db_session.commit()

    token = await _login(client, user.email)
    desc_rows = await _list_rows(client, token, marker, status=status, sortBy="status_changed_at")
    assert [row["trackingId"] for row in desc_rows] == [
        changed_recently.tracking_id,
        changed_earlier.tracking_id,
    ]
    asc_rows = await _list_rows(
        client, token, marker, status=status, sortBy="status_changed_at", sortOrder="asc"
    )
    assert [row["trackingId"] for row in asc_rows] == [
        changed_earlier.tracking_id,
        changed_recently.tracking_id,
    ]


async def test_list_invitations_status_changed_at_requested_column_revert_and_reschedule(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "An invitation whose approval was reverted returns to the top
    of Requested" / "An archived invitation rescheduled back into approval
    is ordered by the reschedule" — and a plain reschedule of a
    never-archived request does not move it."""
    marker = f"req{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    reverted = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=7),
        approval_reverted_at=now - timedelta(minutes=1),
    )
    back_from_archive = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=10),
        archived_at=now - timedelta(days=2),
        rescheduled_at=now - timedelta(minutes=10),
    )
    submitted_today = _build_status_row(
        db_session, branch.id, marker, "submitted", submitted_at=now - timedelta(hours=1)
    )
    plainly_rescheduled = _build_status_row(
        db_session,
        branch.id,
        marker,
        "submitted",
        submitted_at=now - timedelta(days=4),
        rescheduled_at=now - timedelta(seconds=30),
    )
    db_session.add_all([reverted, back_from_archive, submitted_today, plainly_rescheduled])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, status="submitted", sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        reverted.tracking_id,
        back_from_archive.tracking_id,
        submitted_today.tracking_id,
        plainly_rescheduled.tracking_id,
    ]


async def test_list_invitations_status_changed_at_interleaves_mixed_statuses(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Mixed-status list orders by each row's own status time"."""
    marker = f"mix{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    old_submission = now - timedelta(days=2)
    checked_out = _build_status_row(
        db_session,
        branch.id,
        marker,
        "checked_out",
        submitted_at=old_submission,
        checked_in_at=now - timedelta(hours=3),
        checked_out_at=now - timedelta(minutes=2),
    )
    submitted = _build_status_row(
        db_session, branch.id, marker, "submitted", submitted_at=now - timedelta(hours=1)
    )
    approved = _build_status_row(
        db_session,
        branch.id,
        marker,
        "approved",
        submitted_at=old_submission,
        approved_at=now - timedelta(hours=5),
    )
    db_session.add_all([checked_out, submitted, approved])
    await db_session.commit()

    token = await _login(client, user.email)
    rows = await _list_rows(client, token, marker, sortBy="status_changed_at")
    assert [row["trackingId"] for row in rows] == [
        checked_out.tracking_id,
        submitted.tracking_id,
        approved.tracking_id,
    ]


@pytest.mark.parametrize("sort_by", [None, "created_at", "status_changed_at"])
async def test_list_invitations_equal_sort_keys_page_stably(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    sort_by: str | None,
) -> None:
    """spec.md "Equal sort keys page stably" — every row shares one
    timestamp, so only the id tie-breaker decides the order."""
    marker = f"tie{uuid.uuid4().hex[:8]}"
    same_moment = datetime.now(UTC) - timedelta(hours=1)
    invitations = [
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "approved",
            submitted_at=same_moment,
            approved_at=same_moment,
            created_at=same_moment,
        )
        for _ in range(7)
    ]
    db_session.add_all(invitations)
    await db_session.commit()

    token = await _login(client, user.email)
    params: dict[str, Any] = {"search": marker, "pageSize": 2}
    if sort_by is not None:
        params["sortBy"] = sort_by
    seen: list[str] = []
    for page in range(1, 5):
        response = await client.get(
            "/api/v1/invitations",
            params={**params, "page": page},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        seen.extend(row["trackingId"] for row in response.json()["data"])
    assert sorted(seen) == sorted(invitation.tracking_id for invitation in invitations)


async def test_status_changed_at_matches_sql_ordering(
    branch: Branch, db_session: AsyncSession
) -> None:
    """design.md Decision 2 — `service.status_changed_at` (the row field)
    must agree with the SQL expression `sortBy=status_changed_at` orders
    by, for every status and for the revert/reschedule/fallback cases."""
    marker = f"par{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    minutes = iter(range(1, 100))

    def ago() -> datetime:
        return now - timedelta(minutes=next(minutes) * 7)

    invitations = [
        _build_status_row(db_session, branch.id, marker, "submitted", submitted_at=ago()),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=now - timedelta(days=9),
            approval_reverted_at=ago(),
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=now - timedelta(days=9),
            archived_at=now - timedelta(days=8),
            rescheduled_at=ago(),
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "submitted",
            submitted_at=ago(),
            rescheduled_at=now,
        ),
        _build_status_row(
            db_session, branch.id, marker, "approved", submitted_at=ago(), approved_at=ago()
        ),
        _build_status_row(
            db_session, branch.id, marker, "checked_in", submitted_at=ago(), checked_in_at=ago()
        ),
        _build_status_row(
            db_session,
            branch.id,
            marker,
            "checked_out",
            submitted_at=ago(),
            checked_out_at=ago(),
        ),
        _build_status_row(
            db_session, branch.id, marker, "denied", submitted_at=ago(), denied_at=ago()
        ),
        _build_status_row(
            db_session, branch.id, marker, "archived", submitted_at=ago(), archived_at=ago()
        ),
        # Missing status timestamp: falls back to submitted_at.
        _build_status_row(db_session, branch.id, marker, "approved", submitted_at=ago()),
    ]
    db_session.add_all(invitations)
    await db_session.commit()

    rows, total = await InvitationRepository(db_session).list_page(
        branch_scope="all",
        status=None,
        registration_type=None,
        source=None,
        search=marker,
        page=1,
        page_size=100,
        sort_by="status_changed_at",
        sort_order=SortOrder.desc,
    )
    assert total == len(invitations)
    python_order = sorted(
        invitations,
        key=lambda invitation: (
            -invitations_service.status_changed_at(invitation).timestamp(),
            invitation.id,
        ),
    )
    assert [row.id for row in rows] == [invitation.id for invitation in python_order]


async def test_list_invitations_status_changed_at_sort_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/invitations",
        params={"sortBy": "status_changed_at"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_invitations_status_changed_at_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the status-time sort reads only the
    session's own tenant schema."""
    marker = f"iso{uuid.uuid4().hex[:8]}"
    db_session.add(
        _build_status_row(db_session, branch.id, marker, "approved", submitted_at=datetime.now(UTC))
    )
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_status_sort"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope="all",
            status=None,
            registration_type=None,
            source=None,
            search=marker,
            page=1,
            page_size=20,
            sort_by="status_changed_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


async def test_list_invitations_relevant_to_me_host_without_view_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Host sees their own invitation without
    invitations:view" — `relevantToMe` bypasses the branch-scoped
    permission check entirely.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_honours_purpose_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Purpose filter applies in relevantToMe mode"."""
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    delivery = await _invitation_with_host_step(
        db_session, branch.id, host, purpose_of_visit="Delivery"
    )
    interview = await _invitation_with_host_step(
        db_session, branch.id, host, purpose_of_visit="Interview"
    )

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "purposeOfVisit": "Delivery"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert delivery.tracking_id in tracking_ids
    assert interview.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_delegate_sees_delegated_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Delegate sees the invitation they were
    delegated" — regardless of `invitations:view` and regardless of that
    step's current status.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add_all([host, delegate])
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    await _delegate_step(db_session, invitation, delegate, host)

    token = issue_token(delegate)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_reflects_a_re_delegation(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """checkin-approval-workflow-improvements generalizes delegation to
    support re-delegation (chaining) — `relevantToMe`'s existing delegate
    clause is per-step and reads the step's *current* `delegatedToUserId`,
    so it already generalizes correctly: once a step is re-delegated, the
    new delegate sees the invitation and the superseded one no longer does.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    first_delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-1-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="First Delegate",
    )
    second_delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-2-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Second Delegate",
    )
    db_session.add_all([host, first_delegate, second_delegate])
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)
    step = await _delegate_step(db_session, invitation, first_delegate, host)

    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id,
        delegated_to_user_id=second_delegate.id,
        delegated_by_user_id=first_delegate.id,
        expected_current_delegate_id=first_delegate.id,
    )
    await db_session.commit()

    second_token = issue_token(second_delegate)
    second_response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_response.status_code == 200, second_response.text
    assert invitation.tracking_id in {row["trackingId"] for row in second_response.json()["data"]}

    first_token = issue_token(first_delegate)
    first_response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_response.status_code == 200, first_response.text
    assert invitation.tracking_id not in {
        row["trackingId"] for row in first_response.json()["data"]
    }


async def test_list_invitations_relevant_to_me_role_holder_sees_current_step_invitation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder sees an invitation whose
    current step needs their role" — closes the gap where such a user could
    only find the invitation via the unfiltered branch-wide list.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_delegated(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A non-default-role holder loses
    visibility once the step is delegated to someone else"
    (harden-approval-gate-and-narrow-delegate-visibility) — clause (c) now
    requires the current step to be undelegated; a non-default-host-role
    holder who is not the delegate, the resolved host, or a past actor
    loses visibility the moment the step is delegated to someone else. This
    replaces the pre-change assertion that such a role-holder retained
    visibility indefinitely.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_default_host_role_keeps_visibility_once_delegated(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder keeps seeing the invitation
    once someone else's delegation is assigned" — clause (e) is the one
    exception to clause (c)'s narrowing: every holder of the tenant's
    default host role keeps permanent visibility, even once the ownership
    step is delegated to a specific host who is neither them nor anyone who
    acted on the step.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    invitation = await _invitation_with_role_step(db_session, branch.id, reception_role)

    role_holder = _make_role_holder(db_session, reception_role, branch.id)
    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Host",
    )
    db_session.add(host)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).delegate_if_eligible(
        step.id, delegated_to_user_id=host.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_default_host_role_keeps_visibility_after_approval(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md clause (e) — permanent visibility for every
    default-host-role holder does not depend on the invitation's own
    status either: it still holds once the invitation is fully `approved`.
    """
    reception_role = await RoleRepository(db_session).get_by_name("reception")
    assert reception_role is not None
    invitation = await _invitation_with_role_step(db_session, branch.id, reception_role)

    role_holder = _make_role_holder(db_session, reception_role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    other_holder = _make_role_holder(db_session, reception_role, branch.id)
    await db_session.commit()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=other_holder.id
    )
    invitation.status = "approved"
    invitation.approved_at = datetime.now(UTC)
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_step_acted_on(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder loses visibility once the
    step is actually approved or rejected" — clause (c) only matches while
    the role's step is still the current pending one, delegated or not.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    delegate = UserFactory.build(
        id=uuid.uuid4(),
        email=f"delegate-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Delegate",
    )
    db_session.add(delegate)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step_repo = InvitationApprovalStepRepository(db_session)
    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await step_repo.delegate_if_eligible(
        step.id, delegated_to_user_id=delegate.id, delegated_by_user_id=role_holder.id
    )
    await db_session.commit()
    await step_repo.approve_if_pending(step.id, user_id=delegate.id)
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_actor_keeps_visibility_after_own_step_approved(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "The caller who personally approved a step
    keeps seeing the invitation forever, via clause (d)"
    (reception-retains-visibility-and-delegation-after-own-step) — unlike
    clause (c), clause (d) does not drop off once the step the caller acted
    on stops being current.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=role_holder.email, tenant_id=tenant.id, user_id=role_holder.id)
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=role_holder.id
    )
    await db_session.commit()

    token = issue_token(role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_non_actor_role_holder_gains_nothing_from_clause_d(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "clause (d) is keyed to the specific person
    who acted, not to a role" — a different holder of the same role, who
    never personally acted on the step, gains no visibility once it's no
    longer current.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name=f"relevant-role-{uuid.uuid4().hex[:8]}")
    db_session.add(role)
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, role)

    acting_holder = _make_role_holder(db_session, role, branch.id)
    bystander_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(
            email=bystander_holder.email, tenant_id=tenant.id, user_id=bystander_holder.id
        )
    )
    await db_session.commit()

    step = (
        await db_session.execute(
            select(InvitationApprovalStep).where(
                InvitationApprovalStep.invitation_id == invitation.id
            )
        )
    ).scalar_one()
    await InvitationApprovalStepRepository(db_session).approve_if_pending(
        step.id, user_id=acting_holder.id
    )
    await db_session.commit()

    token = issue_token(bystander_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_role_holder_wrong_role_sees_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "A role-holder who is not currently
    authorized on the pending step sees nothing for it".
    """
    step_role = RoleFactory.build(id=uuid.uuid4(), name=f"step-role-{uuid.uuid4().hex[:8]}")
    other_role = RoleFactory.build(id=uuid.uuid4(), name=f"other-role-{uuid.uuid4().hex[:8]}")
    db_session.add_all([step_role, other_role])
    await db_session.flush()
    invitation = await _invitation_with_role_step(db_session, branch.id, step_role)

    mismatched_role_holder = _make_role_holder(db_session, other_role, branch.id)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(
            email=mismatched_role_holder.email,
            tenant_id=tenant.id,
            user_id=mismatched_role_holder.id,
        )
    )
    await db_session.commit()

    token = issue_token(mismatched_role_holder)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_excludes_unrelated_caller(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "Caller who is neither host nor delegate
    sees nothing for that invitation" — even one who holds
    `invitations:view` at that branch.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, branch.id, host)

    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_composes_with_status_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "relevantToMe composes with status
    filtering".
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    submitted = await _invitation_with_host_step(
        db_session, branch.id, host, status="submitted", approved_at=None
    )
    denied = await _invitation_with_host_step(
        db_session, branch.id, host, status="denied", approved_at=None
    )

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "status": "submitted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert submitted.tracking_id in tracking_ids
    assert denied.tracking_id not in tracking_ids


async def test_list_invitations_relevant_to_me_empty_result_is_not_an_error(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    """specs/invitations/spec.md "No relevant invitations returns an empty
    page, not an error" — no `invitations:view` grant needed, and no
    invitation names this caller either.
    """
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


async def test_list_invitations_relevant_to_me_ignores_branch_header(
    client: AsyncClient,
    db_session: AsyncSession,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """specs/invitations/spec.md "X-Branch-ID is ignored when relevantToMe
    is set".
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-RELEVANT")
    db_session.add(other_branch)
    await db_session.flush()
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    invitation = await _invitation_with_host_step(db_session, other_branch.id, host)

    token = issue_token(host)
    response = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200, response.text
    tracking_ids = {row["trackingId"] for row in response.json()["data"]}
    assert invitation.tracking_id in tracking_ids


async def test_list_invitations_relevant_to_me_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — a caller's relevant-to-me set from one
    tenant's schema must not see another tenant's invitations, even for a
    user id that happens to exist in both.
    """
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    await _invitation_with_host_step(db_session, branch.id, host)

    other_schema = "tenant_other_test_invitation_relevant_to_me"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope=None,
            relevant_to_user_id=host.id,
            default_host_role_id=uuid.uuid4(),
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


async def test_list_invitations_relevant_to_me_role_holder_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    """testing-standards.md §2 — the new role-based-current-step-approver
    clause must not leak across tenant schemas either, even when a
    same-named role and the same user id happen to exist in both (roles and
    `UserBranchRole` rows are themselves tenant-scoped tables, per
    `database-architecture.md` §2 — there is nothing shared for a forged or
    coincidental id to reach into).
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="relevant-role-isolation-test")
    db_session.add(role)
    await db_session.flush()
    await _invitation_with_role_step(db_session, branch.id, role)
    role_holder = _make_role_holder(db_session, role, branch.id)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_relevant_to_me_role"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope=None,
            relevant_to_user_id=role_holder.id,
            default_host_role_id=uuid.uuid4(),
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


async def test_invitation_list_page_tenant_schema_isolation(
    make_tenant_schema,
    open_tenant_session,
    branch: Branch,
    db_session: AsyncSession,
) -> None:
    invitation = _build_invitation(db_session, branch.id)
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_invitation_listing"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rows, total = await InvitationRepository(other_session).list_page(
            branch_scope="all",
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
        )
        assert rows == []
        assert total == 0


# --- fix-dashboard-count-accuracy: drill-down list filters --------------------
# specs/invitations/spec.md "Invitation List Supports Dashboard Drill-Down
# Filters". Every row pins `checkin_code`/check-in times/`created_at`, so the
# factory's random values can't leak into a count.


def _drill_down_row(branch_id: uuid.UUID, **overrides: Any):
    now = datetime.now(UTC)
    overrides.setdefault("checkin_code", None)
    overrides.setdefault("check_in_status", "unused")
    overrides.setdefault("checked_in_at", None)
    overrides.setdefault("checked_out_at", None)
    overrides.setdefault("created_at", now)
    overrides.setdefault("preferred_visit_date", now.date())
    overrides.setdefault("expires_at", now + timedelta(hours=6))
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


async def _list_ids(client: AsyncClient, headers: dict[str, str], **params: str) -> set[str]:
    response = await client.get("/api/v1/invitations", params=params, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"]["total"] == len(body["data"])
    return {row["id"] for row in body["data"]}


async def test_list_visit_date_range_filters_by_visit_day(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    today = datetime.now(UTC).date()
    on_day = _drill_down_row(branch.id, preferred_visit_date=today)
    next_day = _drill_down_row(branch.id, preferred_visit_date=today + timedelta(days=1))
    undated_created_today = _drill_down_row(branch.id, preferred_visit_date=None)
    db_session.add_all([on_day, next_day, undated_created_today])
    await db_session.commit()
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    day = today.isoformat()
    assert await _list_ids(client, headers, visitDateFrom=day, visitDateTo=day) == {
        str(on_day.id),
        str(undated_created_today.id),
    }
    assert await _list_ids(
        client, headers, visitDateFrom=(today + timedelta(days=1)).isoformat()
    ) == {str(next_day.id)}


async def test_list_undated_invitation_dated_by_visit_timezone_creation_day(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """Created 23:30 IST on day D (18:00 UTC) — still day D in the visit
    timezone, whatever the UTC date.
    """
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone=_KOLKATA))
    kolkata_day = date(2026, 10, 25)
    created = datetime.combine(kolkata_day, time(23, 30), tzinfo=ZoneInfo(_KOLKATA))
    undated = _drill_down_row(
        branch.id, preferred_visit_date=None, created_at=created.astimezone(UTC)
    )
    db_session.add(undated)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    day = kolkata_day.isoformat()
    assert await _list_ids(client, headers, visitDateFrom=day, visitDateTo=day) == {str(undated.id)}
    next_day = (kolkata_day + timedelta(days=1)).isoformat()
    assert await _list_ids(client, headers, visitDateFrom=next_day, visitDateTo=next_day) == set()


async def test_list_reversed_visit_date_range_rejected(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    response = await client.get(
        "/api/v1/invitations",
        params={"visitDateFrom": "2026-10-27", "visitDateTo": "2026-10-26"},
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_list_upcoming_and_exclude_expired(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    upcoming = _drill_down_row(branch.id, status="approved")
    expired_approved = _drill_down_row(
        branch.id, status="approved", expires_at=now - timedelta(hours=1)
    )
    inside = _drill_down_row(
        branch.id, status="checked_in", check_in_status="checked_in", checked_in_at=now
    )
    open_request = _drill_down_row(branch.id, status="submitted")
    expired_request = _drill_down_row(
        branch.id, status="submitted", expires_at=now - timedelta(days=3)
    )
    db_session.add_all([upcoming, expired_approved, inside, open_request, expired_request])
    await db_session.commit()
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    assert await _list_ids(client, headers, upcoming="true") == {str(upcoming.id)}
    assert await _list_ids(client, headers, status="submitted", excludeExpired="true") == {
        str(open_request.id)
    }
    assert await _list_ids(client, headers, status="submitted") == {
        str(open_request.id),
        str(expired_request.id),
    }


async def test_list_branch_id_narrows_to_an_authorized_branch(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Drill Other", code="DRILLB")
    db_session.add(other)
    await db_session.flush()
    here = _drill_down_row(branch.id)
    there = _drill_down_row(other.id)
    db_session.add_all([here, there])
    await db_session.commit()
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    assert await _list_ids(client, headers, branchId=str(branch.id)) == {str(here.id)}


async def test_list_branch_id_outside_view_all_scope_is_forbidden(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    """The permission-denied case (testing-standards.md §2)."""
    other = BranchFactory.build(id=uuid.uuid4(), name="Drill Forbidden", code="DRILLF")
    db_session.add(other)
    await db_session.commit()
    viewer = await _branch_scoped_invitation_viewer(db_session, tenant, branch.id)
    headers = {"Authorization": f"Bearer {issue_token(viewer)}"}

    response = await client.get(
        "/api/v1/invitations", params={"branchId": str(other.id)}, headers=headers
    )
    assert response.status_code == 403, response.text


async def test_list_branch_id_never_widens_relevant_to_me(
    client: AsyncClient, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    other = BranchFactory.build(id=uuid.uuid4(), name="Drill Host", code="DRILLH")
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example"
    )
    db_session.add_all([other, host])
    await db_session.flush()
    own_here = _drill_down_row(branch.id, host_id=host.id)
    own_there = _drill_down_row(other.id, host_id=host.id)
    not_own_there = _drill_down_row(other.id)
    db_session.add_all([own_here, own_there, not_own_there])
    await db_session.commit()
    headers = {"Authorization": f"Bearer {issue_token(host)}"}

    assert await _list_ids(client, headers, relevantToMe="true", branchId=str(other.id)) == {
        str(own_there.id)
    }


async def test_export_applies_the_drill_down_filters(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    open_request = _drill_down_row(branch.id, status="submitted")
    expired_request = _drill_down_row(
        branch.id, status="submitted", expires_at=now - timedelta(days=3)
    )
    db_session.add_all([open_request, expired_request])
    await db_session.commit()
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    params = {"status": "submitted", "excludeExpired": "true", "branchId": str(branch.id)}

    exported = await client.get("/api/v1/invitations/export", params=params, headers=headers)
    assert exported.status_code == 200, exported.text
    assert {row["Tracking ID"] for row in _csv_rows(exported.content)} == {open_request.tracking_id}


async def test_drill_down_filters_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    """testing-standards.md §2 — the drill-down filters on another tenant's
    schema see none of this schema's rows.
    """
    today = datetime.now(UTC).date()
    db_session.add(_drill_down_row(branch.id, status="approved"))
    await db_session.commit()

    other_schema = "tenant_other_test_drill_down"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        _, total = await InvitationRepository(other_session).list_page(
            branch_scope="all",
            status=None,
            registration_type=None,
            source=None,
            search=None,
            page=1,
            page_size=20,
            sort_by="submitted_at",
            sort_order=SortOrder.desc,
            visit_days=VisitDayRange.local(today, today, ZoneInfo("UTC")),
            upcoming=True,
            now=datetime.now(UTC),
            branch_id=branch.id,
        )
    assert total == 0
