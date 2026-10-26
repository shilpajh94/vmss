import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BranchFactory, InvitationFactory, PermissionFactory, RoleFactory, UserFactory
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password
from vmss_api.dashboard.repository import DashboardRepository
from vmss_api.invitations.repository import VisitDayRange
from vmss_api.invitations.service import _visit_timezone
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


def _build_invitation(db_session: AsyncSession, branch_id: uuid.UUID, **overrides):
    """Same shape as `invitations/tests.py::_build_invitation` — builds (but
    does not add/commit) via the shared `InvitationFactory`
    (testing-standards.md §1) rather than a hand-built dict.

    Unlike `invitations/tests.py`'s version, this also forces `created_at` to
    "now": `TimestampMixin.created_at` is a `server_default`, which
    polyfactory doesn't know about, so an unoverridden build gets a random
    historical Python-side datetime that SQLAlchemy then inserts verbatim
    (overriding the server default) — invisible to every existing test, but
    fatal to this feature's own "visits created today" count, the first
    thing here to actually filter on `created_at`'s value.
    """
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    overrides.setdefault("created_at", datetime.now(UTC))
    return InvitationFactory.build(id=uuid.uuid4(), branch_id=branch_id, **overrides)


async def _branch_scoped_user(
    db_session: AsyncSession,
    tenant: Tenant,
    *,
    branch_ids: list[uuid.UUID],
    permission_code: str,
    role_name: str,
) -> User:
    """A caller holding `permission_code` at exactly `branch_ids` (one role
    grant per branch, no company-wide `None` row) — same posture as
    `invitations/tests.py::_branch_scoped_invitation_viewer`, generalized to
    one-or-more branches so it also backs the "aggregates across every
    authorized branch" scenario.
    """
    permission = PermissionFactory.build(
        id=uuid.uuid4(), code=permission_code, description=permission_code
    )
    role = RoleFactory.build(id=uuid.uuid4(), name=role_name, permissions=[permission])
    branch_roles = [
        UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id) for branch_id in branch_ids
    ]
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{role_name}-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name=role_name,
        branch_roles=branch_roles,
    )
    db_session.add_all([permission, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


@pytest_asyncio.fixture
async def other_branch(db_session: AsyncSession) -> Branch:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other)
    await db_session.commit()
    return other


# --- GET /admin/dashboard/overview -------------------------------------------


async def test_overview_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    pending = _build_invitation(db_session, branch.id, status="submitted")
    upcoming = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=now,
        expires_at=now + timedelta(hours=2),
    )
    expired = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=now,
        expires_at=now - timedelta(hours=1),
    )
    checked_in = _build_invitation(
        db_session, branch.id, status="checked_in", approved_at=now, checked_in_at=now
    )
    checked_out = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        approved_at=now,
        checked_in_at=now,
        checked_out_at=now,
    )
    denied = _build_invitation(db_session, branch.id, status="denied", denied_at=now)
    db_session.add_all([pending, upcoming, expired, checked_in, checked_out, denied])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]

    assert body["visitsTodayCount"] == 6
    assert body["checkedInCount"] == 1
    assert body["pendingApprovalCount"] == 1
    assert body["upcomingVisitorCount"] == 1
    assert [v["id"] for v in body["upcomingVisitors"]] == [str(upcoming.id)]


async def test_overview_upcoming_visitor_preview_includes_tracking_id(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Upcoming-visitors preview rows carry trackingId" — needed so
    the admin portal can call `PATCH /api/v2/invitations/{trackingId}/
    check-in` directly, now that the dashboard's own check-in mutation is
    removed.
    """
    now = datetime.now(UTC)
    upcoming = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        approved_at=now,
        expires_at=now + timedelta(hours=2),
    )
    db_session.add(upcoming)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    [row] = response.json()["data"]["upcomingVisitors"]
    assert row["trackingId"] == upcoming.tracking_id


async def test_overview_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/admin/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_overview_scoped_to_one_branch_via_branch_id(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id, other_branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    other_invitation = _build_invitation(db_session, other_branch.id, status="submitted")
    db_session.add_all([invitation, other_invitation])
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/overview",
        params={"branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["pendingApprovalCount"] == 1


async def test_overview_aggregates_across_authorized_branches_when_branch_id_omitted(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id, other_branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    other_invitation = _build_invitation(db_session, other_branch.id, status="submitted")
    db_session.add_all([invitation, other_invitation])
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["pendingApprovalCount"] == 2


async def test_overview_branch_id_not_authorized_rejected(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/overview",
        params={"branchId": str(other_branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- checkin-approval-workflow-improvements: PATCH /admin/dashboard/upcoming-visitors removed --
# The dashboard's own check-in mutation is gone (spec.md "Check In an
# Upcoming Visitor From the Dashboard" — REMOVED). The admin portal now
# calls `PATCH /api/v2/invitations/{trackingId}/check-in` directly, using
# `trackingId` from the overview's upcoming-visitors preview row — see
# `test_overview_upcoming_visitor_preview_includes_tracking_id` below.


async def test_dashboard_upcoming_visitors_check_in_route_removed(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- GET /admin/dashboard/checkins --------------------------------------------


async def test_list_checkins_success(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    checked_in = _build_invitation(
        db_session, branch.id, status="checked_in", approved_at=now, checked_in_at=now
    )
    checked_out = _build_invitation(
        db_session,
        branch.id,
        status="checked_out",
        approved_at=now,
        checked_in_at=now,
        checked_out_at=now,
    )
    never_checked_in = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add_all([checked_in, checked_out, never_checked_in])
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/checkins", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    ids = {row["id"] for row in body["data"]}
    assert ids == {str(checked_in.id), str(checked_out.id)}


async def test_list_checkins_pagination_metadata(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    invitations = [
        _build_invitation(
            db_session,
            branch.id,
            status="checked_in",
            approved_at=now,
            checked_in_at=now + timedelta(minutes=i),
        )
        for i in range(3)
    ]
    db_session.add_all(invitations)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/checkins",
        params={"pageSize": 2, "page": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["total"] == 3
    assert body["pagination"]["totalPages"] == 2

    second_page = await client.get(
        "/api/v1/admin/dashboard/checkins",
        params={"pageSize": 2, "page": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(second_page.json()["data"]) == 1


async def test_list_checkins_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/admin/dashboard/checkins", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_list_checkins_branch_id_narrows_result(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    now = datetime.now(UTC)
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id, other_branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    in_branch = _build_invitation(
        db_session, branch.id, status="checked_in", approved_at=now, checked_in_at=now
    )
    in_other_branch = _build_invitation(
        db_session, other_branch.id, status="checked_in", approved_at=now, checked_in_at=now
    )
    db_session.add_all([in_branch, in_other_branch])
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/checkins",
        params={"branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert ids == {str(in_branch.id)}


# --- GET /admin/dashboard/search ----------------------------------------------


async def test_search_partial_case_insensitive_match(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", primary_contact_full_name="John Carter"
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/search",
        params={"query": "carter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert ids == {str(invitation.id)}


async def test_search_no_matches_returns_empty_list(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="submitted", primary_contact_full_name="John Carter"
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/search",
        params={"query": "zzz-no-match"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_search_query_below_minimum_length_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/admin/dashboard/search",
        params={"query": "a"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_search_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/admin/dashboard/search",
        params={"query": "carter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_search_results_limited_to_authorized_branches(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    matching_other_branch = _build_invitation(
        db_session, other_branch.id, status="submitted", primary_contact_full_name="Jane Carter"
    )
    db_session.add(matching_other_branch)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/search",
        params={"query": "carter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


# --- Tenant isolation ---------------------------------------------------------


async def test_dashboard_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    """testing-standards.md §2: a query against a *different* tenant schema
    must not see this schema's invitations at all — same shape as
    `invitations/tests.py::test_check_in_repository_tenant_schema_isolation`.
    """
    now = datetime.now(UTC)
    invitation = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        approved_at=now,
        checked_in_at=now,
        primary_contact_full_name="John Carter",
    )
    db_session.add(invitation)
    await db_session.commit()

    other_schema = "tenant_other_test_dashboard"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        repo = DashboardRepository(other_session)
        counts = await repo.overview_counts(
            "all", today=VisitDayRange.local(now.date(), now.date(), ZoneInfo("UTC")), now_utc=now
        )
        assert counts["checked_in_count"] == 0
        assert counts["visits_today_count"] == 0

        rows, total = await repo.paginated_checkins(
            "all", page=1, page_size=20, sort_by="checked_in_at", sort_order=SortOrder.desc
        )
        assert rows == []
        assert total == 0

        results = await repo.search_by_contact_name("all", query="carter", limit=10)
        assert results == []

        preview = await repo.upcoming_visitors_preview("all", now_utc=now, limit=10)
        assert preview == []


# The dashboard's own check-in mutation is removed
# (checkin-approval-workflow-improvements); check-in tenant-isolation is now
# covered exclusively by `invitations/tests.py::
# test_check_in_repository_tenant_schema_isolation`, since check-in is
# entirely an `invitations` capability concern once the dashboard wrapper is
# gone.


# --- "Today" boundary follows tenant timezone --------------------------------


def test_visit_day_range_bounds_follow_the_visit_timezone() -> None:
    """spec.md ""Today" boundary follows tenant timezone" — a pure-function
    check (testing-standards.md §3) at a moment where UTC and a non-UTC
    timezone disagree on the calendar date. `Pacific/Kiritimati` is a fixed
    UTC+14 offset with no DST, so the expected bounds are exact.
    """
    kiritimati = ZoneInfo("Pacific/Kiritimati")
    today = datetime(2026, 1, 1, 23, 0, tzinfo=UTC).astimezone(kiritimati).date()

    bounds = VisitDayRange.local(today, today, kiritimati)

    assert today == date(2026, 1, 2)
    assert bounds.starts_at == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert bounds.ends_before == datetime(2026, 1, 2, 10, 0, tzinfo=UTC)


# --- restrict-delegated-invitation-visibility ----------------------------------


async def test_dashboard_endpoints_reject_host_holding_only_invitations_view(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    """spec.md "A host cannot search visitor names branch-wide" and "A host
    cannot read branch-wide dashboard counts" — `invitations:view` alone no
    longer reaches the branch-wide dashboard.
    """
    host = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view",
        role_name="host",
    )
    db_session.add(_build_invitation(db_session, branch.id, status="submitted"))
    await db_session.commit()
    headers = {"Authorization": f"Bearer {issue_token(host)}"}

    for path, params in (
        ("/api/v1/admin/dashboard/overview", {"branchId": str(branch.id)}),
        ("/api/v1/admin/dashboard/overview", {}),
        ("/api/v1/admin/dashboard/checkins", {}),
        ("/api/v1/admin/dashboard/search", {"query": "carter"}),
    ):
        response = await client.get(path, params=params, headers=headers)
        assert response.status_code == 403, (path, response.text)


# --- staff-lifecycle-emails-and-dashboard-landing: GET /my-overview -----------
# spec.md "Personal Dashboard Overview Scoped to the Caller's Relevant
# Invitations". Counted over the `relevantToMe` predicate, which resolves the
# tenant's default host role — falling back to `reception`, seeded per test
# below the same way `invitations/tests.py::_default_host_role` does.

_MY_OVERVIEW = "/api/v1/admin/dashboard/my-overview"


async def _host_user(db_session: AsyncSession) -> User:
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    host = UserFactory.build(
        id=uuid.uuid4(), email=f"host-{uuid.uuid4().hex[:8]}@acme-test.example", full_name="Host"
    )
    db_session.add(host)
    await db_session.flush()
    return host


def _tenant_today(tenant: Tenant):
    """Today in the visit timezone — the tenant's, since these fixtures seed
    no company row.
    """
    return datetime.now(UTC).astimezone(_visit_timezone(None, tenant)).date()


async def test_my_overview_counts_only_the_callers_own_visits(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    today = _tenant_today(tenant)
    future = datetime.now(UTC) + timedelta(days=1)
    own = [
        _build_invitation(
            db_session,
            branch.id,
            host_id=host.id,
            status="approved",
            check_in_status="unused",
            preferred_visit_date=today,
            expires_at=future,
        ),
        _build_invitation(
            db_session,
            branch.id,
            host_id=host.id,
            status="checked_in",
            check_in_status="checked_in",
            preferred_visit_date=today,
            expires_at=future,
        ),
        _build_invitation(db_session, branch.id, host_id=host.id, status="submitted"),
    ]
    others = [
        _build_invitation(
            db_session,
            branch.id,
            status=status,
            check_in_status="unused",
            preferred_visit_date=today,
            expires_at=future,
        )
        for status in (
            "approved",
            "checked_in",
            "submitted",
            "submitted",
            "approved",
            "denied",
            "approved",
        )
    ]
    db_session.add_all([*own, *others])
    await db_session.commit()

    response = await client.get(
        _MY_OVERVIEW, headers={"Authorization": f"Bearer {issue_token(host)}"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["visitsToday"] == 2
    assert data["insideNow"] == 1
    assert data["awaitingApproval"] == 1
    assert data["upcoming"] == 1
    assert [row["trackingId"] for row in data["upcomingPreview"]] == [own[0].tracking_id]


async def test_my_overview_awaiting_approval_matches_relevant_to_me_list(
    client: AsyncClient, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    db_session.add_all(
        [
            _build_invitation(db_session, branch.id, host_id=host.id, status="submitted")
            for _ in range(3)
        ]
        + [_build_invitation(db_session, branch.id, status="submitted")]
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {issue_token(host)}"}

    overview = await client.get(_MY_OVERVIEW, headers=headers)
    listing = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "status": "submitted"},
        headers=headers,
    )
    assert overview.status_code == 200, overview.text
    assert listing.status_code == 200, listing.text
    assert overview.json()["data"]["awaitingApproval"] == listing.json()["pagination"]["total"]
    assert overview.json()["data"]["awaitingApproval"] == 3


async def test_my_overview_excludes_archived_and_denied(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    today = _tenant_today(tenant)
    db_session.add_all(
        [
            _build_invitation(
                db_session,
                branch.id,
                host_id=host.id,
                status=status,
                check_in_status="unused",
                preferred_visit_date=today,
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
            for status in ("archived", "denied")
        ]
    )
    await db_session.commit()

    response = await client.get(
        _MY_OVERVIEW, headers={"Authorization": f"Bearer {issue_token(host)}"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["visitsToday"], data["insideNow"], data["awaitingApproval"], data["upcoming"]) == (
        0,
        0,
        0,
        0,
    )
    assert data["upcomingPreview"] == []


async def test_my_overview_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(_MY_OVERVIEW)
    assert response.status_code == 401, response.text


async def test_my_overview_ignores_branch_header(
    client: AsyncClient, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    db_session.add(_build_invitation(db_session, branch.id, host_id=host.id, status="submitted"))
    db_session.add(_build_invitation(db_session, branch.id, status="submitted"))
    await db_session.commit()
    token = issue_token(host)

    plain = await client.get(_MY_OVERVIEW, headers={"Authorization": f"Bearer {token}"})
    with_header = await client.get(
        _MY_OVERVIEW,
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(uuid.uuid4())},
    )
    assert plain.status_code == with_header.status_code == 200
    # `generatedAt` is the computation time, so it legitimately differs.
    plain_data = {k: v for k, v in plain.json()["data"].items() if k != "generatedAt"}
    header_data = {k: v for k, v in with_header.json()["data"].items() if k != "generatedAt"}
    assert header_data == plain_data
    assert header_data["awaitingApproval"] == 1


async def test_my_overview_preview_is_capped_and_soonest_first(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    today = _tenant_today(tenant)
    offsets = [5, 2, 8, 1, 7, 3, 6, 4]
    invitations = [
        _build_invitation(
            db_session,
            branch.id,
            host_id=host.id,
            status="approved",
            check_in_status="unused",
            preferred_visit_date=today + timedelta(days=offset),
            preferred_visit_time=None,
            expires_at=datetime.now(UTC) + timedelta(days=offset + 1),
        )
        for offset in offsets
    ]
    db_session.add_all(invitations)
    await db_session.commit()
    expected = [
        inv.tracking_id for inv in sorted(invitations, key=lambda inv: inv.preferred_visit_date)[:5]
    ]

    response = await client.get(
        _MY_OVERVIEW, headers={"Authorization": f"Bearer {issue_token(host)}"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["upcoming"] == 8
    assert [row["trackingId"] for row in data["upcomingPreview"]] == expected


async def test_personal_overview_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    """testing-standards.md §2 — a different tenant schema sees none of this
    schema's invitations, even for the same host id.
    """
    host = await _host_user(db_session)
    now = datetime.now(UTC)
    db_session.add(
        _build_invitation(
            db_session,
            branch.id,
            host_id=host.id,
            status="checked_in",
            check_in_status="checked_in",
            preferred_visit_date=now.date(),
        )
    )
    await db_session.commit()

    other_schema = "tenant_other_test_my_overview"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        repo = DashboardRepository(other_session)
        counts = await repo.personal_overview_counts(
            user_id=host.id,
            default_host_role_id=uuid.uuid4(),
            today=VisitDayRange.local(now.date(), now.date(), ZoneInfo("UTC")),
            now_utc=now,
        )
        assert counts == {
            "visits_today": 0,
            "inside_now": 0,
            "open_awaiting_approval": 0,
            "awaiting_approval": 0,
            "upcoming": 0,
        }
        preview = await repo.personal_upcoming_preview(
            user_id=host.id, default_host_role_id=uuid.uuid4(), now_utc=now, limit=5
        )
        assert preview == []


# --- live-dashboards-and-analytics: overview fields ----------------------------

_OVERVIEW = "/api/v1/admin/dashboard/overview"
_ANALYTICS = "/api/v1/admin/dashboard/analytics"
_MY_ANALYTICS = "/api/v1/admin/dashboard/my-analytics"


async def _get(client: AsyncClient, path: str, token: str, **params) -> dict:
    response = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_overview_scheduled_today_counts_visits_not_creations(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Scheduled-today counts visits, not creations"."""
    today = _tenant_today(tenant)
    future = datetime.now(UTC) + timedelta(days=8)
    visiting_today = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        preferred_visit_date=today,
        expires_at=future,
        created_at=datetime.now(UTC) - timedelta(days=7),
    )
    created_today = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        preferred_visit_date=today + timedelta(days=7),
        expires_at=future,
    )
    db_session.add_all([visiting_today, created_today])
    await db_session.commit()

    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["scheduledTodayCount"] == 1
    assert data["visitsTodayCount"] == 1
    assert data["today"] == today.isoformat()
    assert data["generatedAt"]


async def test_overview_checked_in_today_and_oldest_pending(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Oldest pending submission is reported" plus
    `checkedInTodayCount` (most recent check-in falls today).
    """
    now = datetime.now(UTC)
    oldest = now - timedelta(hours=2)
    db_session.add_all(
        [
            _build_invitation(db_session, branch.id, status="submitted", submitted_at=oldest),
            _build_invitation(
                db_session, branch.id, status="submitted", submitted_at=now - timedelta(hours=1)
            ),
            _build_invitation(
                db_session, branch.id, status="checked_in", approved_at=now, checked_in_at=now
            ),
            _build_invitation(
                db_session,
                branch.id,
                status="checked_out",
                approved_at=now,
                checked_in_at=now - timedelta(days=3),
                checked_out_at=now - timedelta(days=3),
            ),
        ]
    )
    await db_session.commit()

    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["pendingApprovalCount"] == 2
    assert datetime.fromisoformat(data["oldestPendingSubmittedAt"]) == oldest
    assert data["checkedInTodayCount"] == 1


async def test_overview_no_pending_reports_null_oldest(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["pendingApprovalCount"] == 0
    assert data["oldestPendingSubmittedAt"] is None


async def test_overview_upcoming_count_agrees_with_preview_filter(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Upcoming count agrees with the preview filter" — an approved
    invitation already admitted once (re-entry cycle) is neither counted
    nor listed.
    """
    future = datetime.now(UTC) + timedelta(hours=4)
    fresh = [
        _build_invitation(
            db_session, branch.id, status="approved", check_in_status="unused", expires_at=future
        )
        for _ in range(2)
    ]
    readmitted = _build_invitation(
        db_session, branch.id, status="approved", check_in_status="checked_out", expires_at=future
    )
    db_session.add_all([*fresh, readmitted])
    await db_session.commit()

    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["upcomingVisitorCount"] == 2
    assert {row["id"] for row in data["upcomingVisitors"]} == {str(i.id) for i in fresh}


async def test_overview_and_checkins_rows_carry_host_name_and_schedule(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Upcoming-visitors preview rows carry trackingId" and
    "Rows carry the host's name" — resolved server-side, no employee list.
    """
    host = UserFactory.build(
        id=uuid.uuid4(),
        email=f"priya-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name="Priya Nair",
    )
    db_session.add(host)
    await db_session.flush()
    now = datetime.now(UTC)
    visit_date = now.date()
    upcoming = _build_invitation(
        db_session,
        branch.id,
        status="approved",
        host_id=host.id,
        preferred_visit_date=visit_date,
        preferred_visit_time=datetime(2026, 1, 1, 14, 30).time(),
        expires_at=now + timedelta(hours=3),
    )
    unhosted = _build_invitation(
        db_session, branch.id, status="approved", expires_at=now + timedelta(hours=5)
    )
    checked_in = _build_invitation(
        db_session,
        branch.id,
        status="checked_in",
        host_id=host.id,
        approved_at=now,
        checked_in_at=now,
    )
    db_session.add_all([upcoming, unhosted, checked_in])
    await db_session.commit()
    token = await _login(client, user.email)

    rows = (await _get(client, _OVERVIEW, token))["upcomingVisitors"]
    assert rows[0]["trackingId"] == upcoming.tracking_id
    assert rows[0]["hostFullName"] == "Priya Nair"
    assert rows[0]["preferredVisitDate"] == visit_date.isoformat()
    assert rows[0]["preferredVisitTime"] == "14:30:00"
    assert rows[1]["hostFullName"] is None

    response = await client.get(
        "/api/v1/admin/dashboard/checkins", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    [row] = response.json()["data"]
    assert row["hostFullName"] == "Priya Nair"


def test_visits_today_count_is_documented_deprecated() -> None:
    """design.md D2 (deviation recorded in tasks.md 2.4): the field, not the
    route, is deprecated, so it's flagged in the OpenAPI schema.
    """
    from vmss_api.dashboard.schemas import DashboardOverviewOut

    properties = DashboardOverviewOut.model_json_schema(by_alias=True)["properties"]
    assert properties["visitsTodayCount"]["deprecated"] is True
    assert "deprecated" not in properties["scheduledTodayCount"]


# --- live-dashboards-and-analytics: GET /analytics ----------------------------


async def test_analytics_trend_is_zero_filled_and_ordered(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Seven-day trend is zero-filled and ordered"."""
    today = _tenant_today(tenant)
    for offset in (0, 3):
        db_session.add(
            _build_invitation(
                db_session,
                branch.id,
                status="approved",
                preferred_visit_date=today - timedelta(days=offset),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    await db_session.commit()
    token = await _login(client, user.email)

    data = await _get(client, _ANALYTICS, token)
    trend = data["dailyTrend"]
    assert data["range"] == "7d"
    assert [p["date"] for p in trend] == [
        (today - timedelta(days=d)).isoformat() for d in range(6, -1, -1)
    ]
    assert [p["scheduled"] for p in trend] == [0, 0, 0, 1, 0, 0, 1]
    assert len(data["hourlyCheckInsToday"]) == 24

    month = await _get(client, _ANALYTICS, token, range="30d")
    assert len(month["dailyTrend"]) == 30
    assert month["dailyTrend"][-1]["date"] == today.isoformat()


async def test_analytics_trend_separates_attended_and_no_shows(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Trend separates attended visits from no-shows"."""
    yesterday = _tenant_today(tenant) - timedelta(days=1)
    now = datetime.now(UTC)
    attended = [
        _build_invitation(
            db_session,
            branch.id,
            status="checked_out",
            preferred_visit_date=yesterday,
            checked_in_at=now - timedelta(days=1),
            checked_out_at=now - timedelta(days=1),
        )
        for _ in range(3)
    ]
    no_show = _build_invitation(
        db_session,
        branch.id,
        status="archived",
        preferred_visit_date=yesterday,
        archived_at=now,
    )
    # Not a scheduled visit: still awaiting approval for that date.
    pending = _build_invitation(
        db_session, branch.id, status="submitted", preferred_visit_date=yesterday
    )
    db_session.add_all([*attended, no_show, pending])
    await db_session.commit()

    data = await _get(client, _ANALYTICS, await _login(client, user.email))
    point = data["dailyTrend"][-2]
    assert point["date"] == yesterday.isoformat()
    assert (point["scheduled"], point["checkedIn"], point["noShow"]) == (4, 3, 1)


async def test_analytics_hourly_check_ins_use_tenant_local_hours(
    branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Hourly arrivals use the tenant's local hours" — service-level
    (testing-standards.md §3) with an Asia/Kolkata tenant (UTC+05:30, no
    DST), so 09:10 and 09:50 local land in hour 9, not UTC's hour 3/4.
    """
    from zoneinfo import ZoneInfo

    from vmss_api.dashboard.service import get_analytics

    kolkata = ZoneInfo("Asia/Kolkata")
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Kolkata Co",
        slug="kolkata-co",
        schema_name="tenant_kolkata",
        timezone="Asia/Kolkata",
    )
    local_midnight = datetime.now(kolkata).replace(hour=0, minute=0, second=0, microsecond=0)
    for minute in (10, 50):
        checked_in_at = (local_midnight + timedelta(hours=9, minutes=minute)).astimezone(UTC)
        db_session.add(
            _build_invitation(
                db_session, branch.id, status="checked_in", checked_in_at=checked_in_at
            )
        )
    await db_session.commit()

    analytics = await get_analytics(db_session, tenant, "all", range_="7d")
    assert analytics.timezone == "Asia/Kolkata"
    assert [row.hour for row in analytics.hourly_check_ins_today] == list(range(24))
    by_hour = {row.hour: row.count for row in analytics.hourly_check_ins_today}
    assert by_hour[9] == 2
    assert sum(by_hour.values()) == 2


async def test_analytics_status_breakdown_lists_every_status(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Status breakdown includes zero rows", plus the creation-date
    fallback for an invitation with no scheduled visit date.
    """
    today = _tenant_today(tenant)
    db_session.add_all(
        [
            _build_invitation(
                db_session,
                branch.id,
                status="approved",
                preferred_visit_date=today,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            ),
            _build_invitation(
                db_session, branch.id, status="checked_out", preferred_visit_date=today
            ),
            # No visit date: dated by its creation (now) instead.
            _build_invitation(
                db_session, branch.id, status="checked_out", preferred_visit_date=None
            ),
            # Outside the 7-day range.
            _build_invitation(
                db_session,
                branch.id,
                status="denied",
                preferred_visit_date=today - timedelta(days=20),
            ),
        ]
    )
    await db_session.commit()

    data = await _get(client, _ANALYTICS, await _login(client, user.email))
    assert data["statusBreakdown"] == [
        {"status": "submitted", "count": 0},
        {"status": "approved", "count": 1},
        {"status": "checked_in", "count": 0},
        {"status": "checked_out", "count": 2},
        {"status": "denied", "count": 0},
        {"status": "archived", "count": 0},
    ]


async def test_analytics_top_purposes_and_departments(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Top purposes roll the remainder into Other", label fallback
    order (configured name → free text, case-insensitively → "Not
    specified"), and alphabetical tie-breaking.
    """
    from factories import DepartmentFactory, VisitPurposeFactory

    today = _tenant_today(tenant)
    purpose = VisitPurposeFactory.build(id=uuid.uuid4(), name="Interview")
    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=None, name="Finance"
    )
    db_session.add_all([purpose, department])
    await db_session.flush()

    def visit(**overrides):
        fields = {"purpose_of_visit": None, "department_to_visit": None, **overrides}
        return _build_invitation(
            db_session, branch.id, status="checked_out", preferred_visit_date=today, **fields
        )

    rows = [
        visit(purpose_id=purpose.id, department_id=department.id),
        visit(purpose_id=purpose.id, department_id=department.id),
        visit(purpose_id=purpose.id),
        visit(purpose_of_visit="Meeting", department_to_visit="sales"),
        visit(purpose_of_visit="  meeting ", department_to_visit="Sales"),
        visit(purpose_of_visit="Delivery"),
        visit(purpose_of_visit="Audit"),
        visit(purpose_of_visit="Vendor"),
        visit(purpose_of_visit="Training"),
        visit(),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    data = await _get(client, _ANALYTICS, await _login(client, user.email))
    assert data["topPurposes"] == [
        {"label": "Interview", "count": 3},
        {"label": "Meeting", "count": 2},
        {"label": "Audit", "count": 1},
        {"label": "Delivery", "count": 1},
        {"label": "Not specified", "count": 1},
        {"label": "Other", "count": 2},
    ]
    assert data["topDepartments"] == [
        {"label": "Not specified", "count": 6},
        {"label": "Finance", "count": 2},
        {"label": "Sales", "count": 2},
    ]


def test_top_labels_omits_other_when_nothing_remains() -> None:
    from vmss_api.dashboard.service import _top_labels

    result = _top_labels([("A", 2), (None, 1), ("B", 2)])
    assert [(row.label, row.count) for row in result] == [("A", 2), ("B", 2), ("Not specified", 1)]


async def test_analytics_rejects_unknown_range(client: AsyncClient, user: User) -> None:
    """spec.md "Unknown range is rejected"."""
    token = await _login(client, user.email)
    response = await client.get(
        _ANALYTICS, params={"range": "90d"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


async def test_analytics_rejects_host_and_unauthorized_branch(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    """spec.md "A host cannot read branch-wide analytics" and the shared
    branch-scope rejection.
    """
    # Both callers exist before the first request: adding users to the shared
    # test session after a request has run trips MissingGreenlet.
    host = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view",
        role_name="host",
    )
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    host_token, viewer_token = issue_token(host), issue_token(viewer)
    other_branch_id = str(other_branch.id)

    response = await client.get(_ANALYTICS, headers={"Authorization": f"Bearer {host_token}"})
    assert response.status_code == 403, response.text

    response = await client.get(
        _ANALYTICS,
        params={"branchId": other_branch_id},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403, response.text


async def test_analytics_aggregate_excludes_unauthorized_branches(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    """spec.md "Analytics respect branch scope"."""
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view-all",
        role_name="viewer",
    )
    today = _tenant_today(tenant)
    for branch_id in (branch.id, other_branch.id, other_branch.id):
        db_session.add(
            _build_invitation(
                db_session, branch_id, status="checked_out", preferred_visit_date=today
            )
        )
    await db_session.commit()

    data = await _get(client, _ANALYTICS, issue_token(viewer))
    assert data["dailyTrend"][-1]["scheduled"] == 1
    assert sum(row["count"] for row in data["statusBreakdown"]) == 1


# --- live-dashboards-and-analytics: GET /my-analytics -------------------------


async def test_my_analytics_counts_only_the_callers_own_visits(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    """spec.md "A host's analytics contain only their own visits", and
    `X-Branch-ID` doesn't widen the set.
    """
    host = await _host_user(db_session)
    today = _tenant_today(tenant)
    own = [
        _build_invitation(
            db_session, branch.id, host_id=host.id, status=status, preferred_visit_date=today
        )
        for status in ("checked_out", "submitted", "denied")
    ]
    others = [
        _build_invitation(db_session, branch.id, status="checked_out", preferred_visit_date=today)
        for _ in range(7)
    ]
    db_session.add_all([*own, *others])
    await db_session.commit()
    token = issue_token(host)

    data = await _get(client, _MY_ANALYTICS, token)
    assert set(data) == {
        "range",
        "timezone",
        "today",
        "generatedAt",
        "dailyTrend",
        "statusBreakdown",
    }
    assert sum(row["count"] for row in data["statusBreakdown"]) == 3
    assert data["dailyTrend"][-1]["scheduled"] == 1

    response = await client.get(
        _MY_ANALYTICS,
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["data"]["statusBreakdown"] == data["statusBreakdown"]


async def test_my_analytics_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(_MY_ANALYTICS)
    assert response.status_code == 401


async def test_analytics_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    """testing-standards.md §2 — another tenant schema's analytics queries
    see none of this schema's invitations.
    """
    now = datetime.now(UTC)
    db_session.add(
        _build_invitation(
            db_session,
            branch.id,
            status="checked_out",
            preferred_visit_date=now.date(),
            checked_in_at=now,
            purpose_of_visit="Meeting",
        )
    )
    await db_session.commit()

    other_schema = "tenant_other_test_dashboard_analytics"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        repo = DashboardRepository(other_session)
        utc = ZoneInfo("UTC")
        days = VisitDayRange.local(now.date() - timedelta(days=6), now.date(), utc)
        today = VisitDayRange.local(now.date(), now.date(), utc)
        assert await repo.daily_trend(None, days=days, timezone="UTC") == []
        assert await repo.status_breakdown(None, days=days) == []
        assert await repo.top_purposes(None, days=days) == []
        assert await repo.hourly_check_ins(None, timezone="UTC", today=today) == []


# --- fix-dashboard-count-accuracy ---------------------------------------------
# Every count equals the total of the list it drills into, and figures on one
# page agree. Rows pin `checkin_code`, check-in times, `created_at` and
# `expires_at`, so the factory's random values can't leak into a count.


def _visit(branch_id: uuid.UUID, **overrides):
    now = datetime.now(UTC)
    overrides.setdefault("checkin_code", None)
    overrides.setdefault("check_in_status", "unused")
    overrides.setdefault("checked_in_at", None)
    overrides.setdefault("checked_out_at", None)
    overrides.setdefault("submitted_at", now)
    overrides.setdefault("expires_at", now + timedelta(hours=6))
    return _build_invitation(None, branch_id, **overrides)  # type: ignore[arg-type]


def _mixed_visits(branch_id: uuid.UUID, today: date) -> list:
    """One of everything a dashboard figure can include or exclude."""
    now = datetime.now(UTC)
    past = now - timedelta(days=3)
    tomorrow = today + timedelta(days=1)
    return [
        _visit(branch_id, status="approved", preferred_visit_date=today),
        _visit(
            branch_id,
            status="checked_in",
            check_in_status="checked_in",
            checked_in_at=now,
            preferred_visit_date=today,
        ),
        _visit(
            branch_id,
            status="checked_out",
            check_in_status="checked_out",
            checked_in_at=now,
            checked_out_at=now,
            preferred_visit_date=today,
        ),
        # Scheduled for tomorrow but checked in today: on site, not "expected".
        _visit(
            branch_id,
            status="checked_in",
            check_in_status="checked_in",
            checked_in_at=now,
            preferred_visit_date=tomorrow,
        ),
        _visit(branch_id, status="approved", preferred_visit_date=tomorrow),
        _visit(
            branch_id,
            status="approved",
            preferred_visit_date=today - timedelta(days=1),
            expires_at=past,
        ),
        _visit(branch_id, status="archived", preferred_visit_date=today, expires_at=past),
        _visit(branch_id, status="denied", preferred_visit_date=today),
        _visit(branch_id, status="submitted", preferred_visit_date=today),
        _visit(
            branch_id,
            status="submitted",
            preferred_visit_date=today - timedelta(days=3),
            expires_at=past,
            submitted_at=past,
        ),
        # No visit date: dated by its creation day (today).
        _visit(branch_id, status="approved", preferred_visit_date=None),
    ]


async def _list_total(client: AsyncClient, token: str, **params) -> int:
    response = await client.get(
        "/api/v1/invitations", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    return response.json()["pagination"]["total"]


async def test_overview_counts_equal_their_drill_down_lists(
    client: AsyncClient,
    user: User,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
) -> None:
    """spec.md "Counts equal the totals of their drill-down lists" and
    "Status breakdown equals its drill-down list", narrowed to one branch
    while the other branch holds the same mix.
    """
    today = _tenant_today(tenant)
    db_session.add_all([*_mixed_visits(branch.id, today), *_mixed_visits(other_branch.id, today)])
    await db_session.commit()
    token = await _login(client, user.email)
    scope = {"branchId": str(branch.id)}

    overview = await _get(client, _OVERVIEW, token, **scope)
    day = today.isoformat()
    expected_today = 0
    for status in ("approved", "checked_in", "checked_out"):
        expected_today += await _list_total(
            client, token, status=status, visitDateFrom=day, visitDateTo=day, **scope
        )
    assert overview["scheduledTodayCount"] == expected_today == 4
    assert overview["checkedInCount"] == await _list_total(
        client, token, status="checked_in", **scope
    )
    assert overview["openPendingApprovalCount"] == await _list_total(
        client, token, status="submitted", excludeExpired="true", **scope
    )
    assert overview["upcomingVisitorCount"] == await _list_total(
        client, token, upcoming="true", **scope
    )

    analytics = await _get(client, _ANALYTICS, token, range="7d", **scope)
    first_day = analytics["dailyTrend"][0]["date"]
    for row in analytics["statusBreakdown"]:
        assert row["count"] == await _list_total(
            client, token, status=row["status"], visitDateFrom=first_day, visitDateTo=day, **scope
        ), row


async def test_my_overview_counts_equal_their_drill_down_lists(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    host = await _host_user(db_session)
    today = _tenant_today(tenant)
    own = _mixed_visits(branch.id, today)
    for row in own:
        row.host_id = host.id
    db_session.add_all([*own, *_mixed_visits(branch.id, today)])
    await db_session.commit()
    token = issue_token(host)

    data = await _get(client, _MY_OVERVIEW, token)
    mine = {"relevantToMe": "true"}
    day = today.isoformat()
    visits_today = 0
    for status in ("approved", "checked_in", "checked_out"):
        visits_today += await _list_total(
            client, token, status=status, visitDateFrom=day, visitDateTo=day, **mine
        )
    assert data["visitsToday"] == visits_today == 4
    assert data["insideNow"] == await _list_total(client, token, status="checked_in", **mine)
    assert data["openAwaitingApproval"] == await _list_total(
        client, token, status="submitted", excludeExpired="true", **mine
    )
    assert data["openAwaitingApproval"] == 1
    assert data["awaitingApproval"] == 2
    assert data["upcoming"] == await _list_total(client, token, upcoming="true", **mine)


async def test_overview_checked_in_so_far_never_exceeds_expected_today(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    today = _tenant_today(tenant)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            _visit(branch.id, status="approved", preferred_visit_date=today),
            _visit(
                branch.id,
                status="checked_in",
                check_in_status="checked_in",
                checked_in_at=now,
                preferred_visit_date=today,
            ),
            _visit(
                branch.id,
                status="checked_in",
                check_in_status="checked_in",
                checked_in_at=now,
                preferred_visit_date=today + timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()

    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["scheduledTodayCount"] == 2
    assert data["scheduledTodayCheckedInCount"] == 1
    assert data["checkedInTodayCount"] == 2


async def test_overview_open_pending_excludes_expired_requests(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    oldest_open = now - timedelta(hours=2)
    expired_submitted = now - timedelta(days=5)
    db_session.add_all(
        [
            _visit(branch.id, status="submitted", submitted_at=oldest_open),
            _visit(branch.id, status="submitted", submitted_at=now - timedelta(hours=1)),
            _visit(
                branch.id,
                status="submitted",
                submitted_at=expired_submitted,
                expires_at=now - timedelta(days=3),
            ),
        ]
    )
    await db_session.commit()

    data = await _get(client, _OVERVIEW, await _login(client, user.email))
    assert data["openPendingApprovalCount"] == 2
    assert datetime.fromisoformat(data["oldestOpenPendingSubmittedAt"]) == oldest_open
    assert data["pendingApprovalCount"] == 3
    assert datetime.fromisoformat(data["oldestPendingSubmittedAt"]) == expired_submitted


async def test_analytics_today_point_agrees_with_overview(
    client: AsyncClient, user: User, tenant: Tenant, branch: Branch, db_session: AsyncSession
) -> None:
    today = _tenant_today(tenant)
    db_session.add_all(_mixed_visits(branch.id, today))
    await db_session.commit()
    token = await _login(client, user.email)

    overview = await _get(client, _OVERVIEW, token)
    analytics = await _get(client, _ANALYTICS, token, range="7d")
    today_point = analytics["dailyTrend"][-1]
    assert today_point["date"] == today.isoformat()
    assert today_point["checkedIn"] == overview["scheduledTodayCheckedInCount"]
    assert today_point["scheduled"] == overview["scheduledTodayCount"] + today_point["noShow"]
    by_status = {row["status"]: row["count"] for row in analytics["statusBreakdown"]}
    # Today's, yesterday's expired one, and the undated one (dated by its
    # creation day); tomorrow's is outside the range.
    assert by_status["approved"] == 3


async def test_dashboard_uses_the_company_timezone(
    branch: Branch, db_session: AsyncSession
) -> None:
    """spec.md "Dashboard uses the company's timezone, not only the
    tenant's" — a UTC tenant whose company runs on Asia/Kolkata.
    """
    from factories import CompanyFactory
    from vmss_api.dashboard.service import get_analytics, get_overview

    kolkata = ZoneInfo("Asia/Kolkata")
    db_session.add(CompanyFactory.build(id=uuid.uuid4(), default_timezone="Asia/Kolkata"))
    tenant = Tenant(
        id=uuid.uuid4(), name="UTC Co", slug="utc-co", schema_name="tenant_utc", timezone="UTC"
    )
    ist_today = datetime.now(kolkata).date()
    checked_in_at = datetime.combine(ist_today, time(1, 30), tzinfo=kolkata).astimezone(UTC)
    db_session.add(
        _visit(
            branch.id,
            status="checked_in",
            check_in_status="checked_in",
            checked_in_at=checked_in_at,
            preferred_visit_date=ist_today,
        )
    )
    await db_session.commit()

    overview = await get_overview(db_session, tenant, "all")
    analytics = await get_analytics(db_session, tenant, "all", range_="7d")
    assert overview.today == ist_today
    assert overview.scheduled_today_count == 1
    assert analytics.timezone == "Asia/Kolkata"
    by_hour = {row.hour: row.count for row in analytics.hourly_check_ins_today}
    assert by_hour[1] == 1
