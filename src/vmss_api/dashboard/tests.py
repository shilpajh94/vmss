import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BranchFactory, InvitationFactory, PermissionFactory, RoleFactory, UserFactory
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password
from vmss_api.dashboard.repository import DashboardRepository
from vmss_api.dashboard.service import _resolve_tenant_timezone, _today_bounds_utc
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
        permission_code="invitations:view",
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
        permission_code="invitations:view",
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
        permission_code="invitations:view",
        role_name="viewer",
    )
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/admin/dashboard/overview",
        params={"branchId": str(other_branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- PATCH /admin/dashboard/upcoming-visitors --------------------------------


async def test_check_in_upcoming_visitor_success(
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
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "checked_in"

    await db_session.refresh(invitation)
    assert invitation.status == "checked_in"
    assert invitation.checked_in_by_user_id == user.id


async def test_check_in_upcoming_visitor_non_approved_rejected(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(db_session, branch.id, status="submitted")
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "submitted"


async def test_check_in_upcoming_visitor_watchlist_flagged_blocked(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
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

    token = await _login(client, user.email)
    response = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


async def test_check_in_upcoming_visitor_idempotency_key_replay(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession
) -> None:
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "dashboard-checkin-key-1"}

    first = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers=headers,
    )
    second = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


async def test_check_in_upcoming_visitor_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    branch: Branch,
    issue_token,
) -> None:
    viewer = await _branch_scoped_user(
        db_session,
        tenant,
        branch_ids=[branch.id],
        permission_code="invitations:view",
        role_name="viewer-no-checkin",
    )
    invitation = _build_invitation(
        db_session, branch.id, status="approved", approved_at=datetime.now(UTC)
    )
    db_session.add(invitation)
    await db_session.commit()

    token = issue_token(viewer)
    response = await client.patch(
        "/api/v1/admin/dashboard/upcoming-visitors",
        json={"invitationId": str(invitation.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    await db_session.refresh(invitation)
    assert invitation.status == "approved"


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
        permission_code="invitations:view",
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
        permission_code="invitations:view",
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
            "all",
            day_start_utc=now - timedelta(days=1),
            day_end_utc=now + timedelta(days=1),
            now_utc=now,
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


# --- "Today" boundary follows tenant timezone --------------------------------


def test_today_bounds_utc_follows_tenant_timezone() -> None:
    """spec.md ""Today" boundary follows tenant timezone" — a pure-function
    check (testing-standards.md §3) at a moment where UTC and a non-UTC
    tenant timezone disagree on the calendar date. `Pacific/Kiritimati` is a
    fixed UTC+14 offset with no DST, so the expected bounds are exact.
    """
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Kiritimati Co",
        slug="kiritimati-co",
        schema_name="tenant_kiritimati",
        timezone="Pacific/Kiritimati",
    )
    now_utc = datetime(2026, 1, 1, 23, 0, tzinfo=UTC)

    day_start_utc, day_end_utc = _today_bounds_utc(tenant, now_utc=now_utc)

    assert day_start_utc == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert day_end_utc == datetime(2026, 1, 2, 10, 0, tzinfo=UTC)


def test_resolve_tenant_timezone_falls_back_to_utc_for_invalid_value() -> None:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Bad TZ Co",
        slug="bad-tz-co",
        schema_name="tenant_bad_tz",
        timezone="not-a-real-zone",
    )

    assert _resolve_tenant_timezone(tenant).key == "UTC"
