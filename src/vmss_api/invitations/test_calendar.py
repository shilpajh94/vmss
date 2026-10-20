"""specs/invitation-calendar (add-staff-calendar): `GET /invitations/calendar`.

Kept out of the 15k-line `tests.py`; its autouse fixtures don't apply here,
so the tenant's default host role (`reception`) is seeded per test.
"""

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BranchFactory,
    InvitationFactory,
    InvitationVisitorFactory,
    PermissionFactory,
    RoleFactory,
    UserFactory,
)
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.invitations import service
from vmss_api.invitations.models import Invitation
from vmss_api.invitations.repository import CalendarCriteria, InvitationRepository
from vmss_api.org_structure.models import Branch
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant

_CALENDAR = "/api/v1/invitations/calendar"
_OCTOBER = {"from": "2026-10-01", "to": "2026-10-31"}
_EVENT_KEYS = {
    "id",
    "trackingId",
    "status",
    "source",
    "date",
    "time",
    "expectedDuration",
    "checkedInAt",
    "checkedOutAt",
    "primaryContactFullName",
    "visitorCount",
    "hostId",
    "hostFullName",
    "branchId",
    "branchName",
    "buildingName",
    "purposeOfVisit",
    "visitorCategoryName",
    "visitorCategoryBadgeColor",
}


def _invitation(branch_id: uuid.UUID, visit_date: date | None, **overrides: Any) -> Invitation:
    overrides.setdefault("status", "approved")
    overrides.setdefault("created_by_user_id", None)
    overrides.setdefault("registration_type", "individual")
    overrides.setdefault("source", "staff_pre_registration")
    overrides.setdefault("preferred_visit_time", None)
    overrides.setdefault("expected_duration", None)
    overrides.setdefault("created_at", datetime.now(UTC))
    # Unpinned in `InvitationFactory`; a random value (often "") collides on
    # its unique index.
    overrides.setdefault("checkin_code", None)
    return InvitationFactory.build(
        id=uuid.uuid4(), branch_id=branch_id, preferred_visit_date=visit_date, **overrides
    )


async def _staff_user(
    db_session: AsyncSession,
    tenant: Tenant,
    *,
    role_name: str,
    permission_codes: list[str],
    branch_ids: list[uuid.UUID],
) -> User:
    """A caller holding `role_name` at exactly `branch_ids` — same posture as
    `dashboard/tests.py::_branch_scoped_user`, with several permissions.
    Permission codes are unique in the global catalog (and the admin `user`
    fixture may already have inserted them), so existing rows are reused.
    """
    existing = {
        permission.code: permission
        for permission in (
            await db_session.scalars(
                select(Permission).where(Permission.code.in_(permission_codes))
            )
        )
    }
    created = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in permission_codes
        if code not in existing
    ]
    permissions = [*existing.values(), *created]
    role = RoleFactory.build(id=uuid.uuid4(), name=role_name, permissions=permissions)
    staff = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{role_name}-{uuid.uuid4().hex[:8]}@acme-test.example",
        full_name=f"{role_name.title()} User",
        branch_roles=[
            UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
            for branch_id in branch_ids
        ],
    )
    db_session.add_all([*created, role, staff])
    await db_session.flush()
    db_session.add(TenantUserIndex(email=staff.email, tenant_id=tenant.id, user_id=staff.id))
    await db_session.commit()
    return staff


async def _seed_reception_role(db_session: AsyncSession) -> None:
    db_session.add(RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[]))
    await db_session.commit()


async def _host(db_session: AsyncSession, tenant: Tenant, name: str = "Host") -> User:
    """A seeded `host`: `invitations:view` only, no `view-all`."""
    host = await _staff_user(
        db_session,
        tenant,
        role_name=f"host-{uuid.uuid4().hex[:6]}",
        permission_codes=["invitations:view"],
        branch_ids=[],
    )
    host.full_name = name
    await db_session.commit()
    return host


async def _reception(db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID) -> User:
    return await _staff_user(
        db_session,
        tenant,
        role_name="reception",
        permission_codes=["invitations:view", "invitations:view-all"],
        branch_ids=[branch_id],
    )


@pytest_asyncio.fixture
async def other_branch(db_session: AsyncSession) -> Branch:
    other = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other)
    await db_session.commit()
    return other


async def _feed(
    client: AsyncClient,
    token: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = await client.get(
        _CALENDAR,
        params=params or _OCTOBER,
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def _ids(feed: dict[str, Any]) -> set[str]:
    return {event["id"] for event in feed["events"]}


def _sid(*rows: Invitation) -> set[str]:
    """Expected ids, taken before any request: a request expires the shared
    session's objects, and touching `row.id` afterwards would lazy-load
    outside a greenlet (MissingGreenlet).
    """
    return {str(row.id) for row in rows}


# --- Range --------------------------------------------------------------------


async def test_range_is_inclusive_and_bounded(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    before, first, last, after = (
        _invitation(branch.id, day)
        for day in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 31), date(2026, 11, 1))
    )
    deleted = _invitation(branch.id, date(2026, 10, 15), deleted_at=datetime.now(UTC))
    db_session.add_all([before, first, last, after, deleted])
    await db_session.commit()
    expected = _sid(first, last)

    feed = await _feed(client, issue_token(user))

    assert _ids(feed) == expected
    assert sum(day["total"] for day in feed["days"]) == 2
    assert feed["from"] == "2026-10-01" and feed["to"] == "2026-10-31"


async def test_range_validation(client: AsyncClient, user: User, issue_token) -> None:
    headers = {"Authorization": f"Bearer {issue_token(user)}"}
    for params in (
        {"from": "2026-10-01", "to": "2026-11-12"},  # 43 days
        {"from": "2026-10-10", "to": "2026-10-01"},
        {"from": "2026-10-01"},
        {"from": "2026-10-01", "to": "not-a-date"},
    ):
        response = await client.get(_CALENDAR, params=params, headers=headers)
        assert response.status_code == 422, (params, response.text)

    response = await client.get(
        _CALENDAR, params={"from": "2026-10-01", "to": "2026-11-11"}, headers=headers
    )
    assert response.status_code == 200, response.text


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(_CALENDAR, params=_OCTOBER)
    assert response.status_code == 401
    assert response.json()["success"] is False


# --- Event date -----------------------------------------------------------------


async def test_event_date_rules(
    client: AsyncClient,
    user: User,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    tenant.timezone = "Asia/Kolkata"
    late = _invitation(
        branch.id,
        date(2026, 10, 14),
        status="checked_in",
        checked_in_at=datetime(2026, 10, 15, 6, 0, tzinfo=UTC),
    )
    rescheduled = _invitation(
        branch.id, date(2026, 10, 20), previous_preferred_visit_date=date(2026, 10, 14)
    )
    # 20:00Z on the 14th is 01:30 on the 15th in Asia/Kolkata.
    legacy = _invitation(
        branch.id,
        None,
        status="checked_out",
        checked_in_at=datetime(2026, 10, 14, 20, 0, tzinfo=UTC),
        checked_out_at=datetime(2026, 10, 14, 21, 0, tzinfo=UTC),
    )
    walk_in = _invitation(branch.id, date(2026, 10, 14), source="visitor_walk_in")
    db_session.add_all([late, rescheduled, legacy, walk_in])
    await db_session.commit()
    late_id, rescheduled_id, legacy_id, walk_in_id = (
        str(row.id) for row in (late, rescheduled, legacy, walk_in)
    )
    token = issue_token(user)

    feed = await _feed(client, token, {"from": "2026-10-14", "to": "2026-10-20"})
    events = feed["events"]
    by_id = {event["id"]: event for event in events}
    assert feed["timezone"] == "Asia/Kolkata"
    assert by_id[late_id]["date"] == "2026-10-14"
    assert by_id[late_id]["checkedInAt"].startswith("2026-10-15")
    assert by_id[rescheduled_id]["date"] == "2026-10-20"
    assert [event["id"] for event in events].count(rescheduled_id) == 1
    assert by_id[legacy_id]["date"] == "2026-10-15"
    assert by_id[walk_in_id]["source"] == "visitor_walk_in"
    totals = {day["date"]: day["total"] for day in feed["days"]}
    assert totals["2026-10-14"] == 2  # late + walk-in
    assert totals["2026-10-15"] == 1  # legacy fallback

    only_14th = await _feed(client, token, {"from": "2026-10-14", "to": "2026-10-14"})
    assert _ids(only_14th) == {late_id, walk_in_id}


# --- Scope ----------------------------------------------------------------------


async def test_host_sees_only_their_own_visitors(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    host = await _host(db_session, tenant)
    other_host = await _host(db_session, tenant, name="Other Host")
    own = _invitation(branch.id, date(2026, 10, 5), host_id=host.id)
    others = _invitation(branch.id, date(2026, 10, 5), host_id=other_host.id)
    db_session.add_all([own, others])
    await db_session.commit()
    expected = _sid(own)

    feed = await _feed(client, issue_token(host))

    assert feed["scope"] == "mine"
    assert _ids(feed) == expected


async def test_host_asking_for_branch_scope_is_refused(
    client: AsyncClient, tenant: Tenant, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    host = await _host(db_session, tenant)

    response = await client.get(
        _CALENDAR,
        params={**_OCTOBER, "scope": "branch"},
        headers={"Authorization": f"Bearer {issue_token(host)}"},
    )

    assert response.status_code == 403, response.text


async def test_reception_sees_only_their_authorized_branch(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    reception = await _reception(db_session, tenant, branch.id)
    here = _invitation(branch.id, date(2026, 10, 5))
    there = _invitation(other_branch.id, date(2026, 10, 5))
    db_session.add_all([here, there])
    await db_session.commit()
    expected = _sid(here)
    other_branch_id = str(other_branch.id)
    token = issue_token(reception)

    feed = await _feed(client, token)
    assert feed["scope"] == "branch"
    assert _ids(feed) == expected

    response = await client.get(
        _CALENDAR,
        params=_OCTOBER,
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": other_branch_id},
    )
    assert response.status_code == 403, response.text


async def test_security_sees_uninvolved_branch_visits(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    security = await _staff_user(
        db_session,
        tenant,
        role_name="security",
        permission_codes=["invitations:view", "invitations:view-all", "invitations:checkin"],
        branch_ids=[branch.id],
    )
    host = await _host(db_session, tenant)
    visits = [_invitation(branch.id, date(2026, 10, 9), host_id=host.id) for _ in range(3)]
    elsewhere = _invitation(other_branch.id, date(2026, 10, 9))
    db_session.add_all([*visits, elsewhere])
    await db_session.commit()
    expected = _sid(*visits)

    feed = await _feed(client, issue_token(security))

    assert feed["scope"] == "branch"
    assert _ids(feed) == expected


async def test_admin_branch_header_narrows_the_feed(
    client: AsyncClient,
    user: User,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    here = _invitation(branch.id, date(2026, 10, 5))
    there = _invitation(other_branch.id, date(2026, 10, 5))
    db_session.add_all([here, there])
    await db_session.commit()
    both, only_there = _sid(here, there), _sid(there)
    other_branch_id = str(other_branch.id)
    token = issue_token(user)

    everywhere = await _feed(client, token)
    narrowed = await _feed(client, token, headers={"X-Branch-ID": other_branch_id})

    assert _ids(everywhere) == both
    assert _ids(narrowed) == only_there


async def test_branch_viewer_can_ask_for_their_personal_set(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    reception = await _reception(db_session, tenant, branch.id)
    db_session.add_all([_invitation(branch.id, date(2026, 10, 5)) for _ in range(2)])
    await db_session.commit()
    token = issue_token(reception)

    feed = await _feed(client, token, {**_OCTOBER, "scope": "mine"})
    listing = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert feed["scope"] == "mine"
    assert len(feed["events"]) == 2
    assert _ids(feed) == {row["id"] for row in listing.json()["data"]}


async def test_host_calendar_matches_relevant_to_me_list(
    client: AsyncClient, tenant: Tenant, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    """Spec "Calendar and list never disagree for a host"."""
    await _seed_reception_role(db_session)
    host = await _host(db_session, tenant)
    in_range = [
        _invitation(branch.id, date(2026, 10, day), host_id=host.id, status=status)
        for day, status in ((3, "submitted"), (12, "approved"), (28, "checked_out"))
    ]
    out_of_range = _invitation(branch.id, date(2026, 11, 3), host_id=host.id)
    unrelated = _invitation(branch.id, date(2026, 10, 12))
    db_session.add_all([*in_range, out_of_range, unrelated])
    await db_session.commit()
    expected, out_of_range_ids = _sid(*in_range), _sid(out_of_range)
    token = issue_token(host)

    feed = await _feed(client, token)
    listing = await client.get(
        "/api/v1/invitations",
        params={"relevantToMe": "true", "pageSize": 100},
        headers={"Authorization": f"Bearer {token}"},
    )

    listed = {row["id"] for row in listing.json()["data"]}
    assert _ids(feed) == listed - out_of_range_ids
    assert _ids(feed) == expected


async def test_calendar_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    """testing-standards.md §2 — same shape as
    `dashboard/tests.py::test_dashboard_repository_tenant_schema_isolation`.
    """
    db_session.add(_invitation(branch.id, date(2026, 10, 5)))
    await db_session.commit()
    criteria = CalendarCriteria(
        branch_scope="all",
        relevant_to_user_id=None,
        default_host_role_id=None,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
        starts_at=datetime(2026, 10, 1, tzinfo=UTC),
        ends_before=datetime(2026, 11, 1, tzinfo=UTC),
        timezone="UTC",
        statuses=("approved",),
    )

    assert await InvitationRepository(db_session).calendar_events(criteria, limit=10)

    other_schema = "tenant_other_test_calendar"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        repository = InvitationRepository(other_session)
        assert await repository.calendar_events(criteria, limit=10) == []
        assert await repository.calendar_day_totals(criteria) == {}


# --- Status filter ----------------------------------------------------------------


async def test_status_filter(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    statuses = ("submitted", "approved", "checked_in", "checked_out", "archived", "denied")
    rows = {status: _invitation(branch.id, date(2026, 10, 7), status=status) for status in statuses}
    db_session.add_all(rows.values())
    await db_session.commit()
    ids = {status: str(row.id) for status, row in rows.items()}
    token = issue_token(user)

    default = await _feed(client, token)
    assert _ids(default) == {ids[s] for s in statuses if s != "denied"}

    filtered = await _feed(client, token, {**_OCTOBER, "status": ["checked_in", "checked_out"]})
    assert _ids(filtered) == {ids["checked_in"], ids["checked_out"]}
    assert sum(day["total"] for day in filtered["days"]) == 2

    with_denied = await _feed(client, token, {**_OCTOBER, "status": ["denied"]})
    assert _ids(with_denied) == {ids["denied"]}

    response = await client.get(
        _CALENDAR,
        params={**_OCTOBER, "status": "pending-ish"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text


# --- Totals and cap -----------------------------------------------------------------


async def test_days_are_zero_filled_and_exact_when_truncated(
    client: AsyncClient,
    user: User,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
    monkeypatch,
) -> None:
    await _seed_reception_role(db_session)
    db_session.add_all(
        [_invitation(branch.id, date(2026, 10, 2)) for _ in range(3)]
        + [_invitation(branch.id, date(2026, 10, 6)) for _ in range(2)]
    )
    await db_session.commit()
    token = issue_token(user)
    week = {"from": "2026-10-01", "to": "2026-10-07"}

    feed = await _feed(client, token, week)
    assert [day["date"] for day in feed["days"]] == [f"2026-10-0{d}" for d in range(1, 8)]
    assert [day["total"] for day in feed["days"]] == [0, 3, 0, 0, 0, 2, 0]
    assert feed["truncated"] is False

    monkeypatch.setattr(service, "CALENDAR_EVENT_LIMIT", 4)
    capped = await _feed(client, token, week)
    assert capped["truncated"] is True
    assert len(capped["events"]) == 4
    assert sum(day["total"] for day in capped["days"]) == 5
    assert [event["date"] for event in capped["events"]] == ["2026-10-02"] * 3 + ["2026-10-06"]


async def test_events_are_ordered_by_date_time_then_name(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    day = date(2026, 10, 8)
    anytime = _invitation(branch.id, day, primary_contact_full_name="Ann")
    zed = _invitation(branch.id, day, preferred_visit_time=time(9), primary_contact_full_name="Zed")
    bob = _invitation(branch.id, day, preferred_visit_time=time(9), primary_contact_full_name="Bob")
    earlier_day = _invitation(branch.id, date(2026, 10, 3), preferred_visit_time=time(17))
    db_session.add_all([anytime, zed, bob, earlier_day])
    await db_session.commit()
    expected = [str(row.id) for row in (earlier_day, bob, zed, anytime)]

    feed = await _feed(client, issue_token(user))

    assert [event["id"] for event in feed["events"]] == expected
    assert feed["events"][1]["time"] == "09:00:00"
    assert feed["events"][3]["time"] is None


# --- Shape --------------------------------------------------------------------------


async def test_event_shape_has_display_fields_only(
    client: AsyncClient,
    user: User,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    host = await _host(db_session, tenant, name="Priya Host")
    group = _invitation(
        branch.id,
        date(2026, 10, 10),
        host_id=host.id,
        registration_type="group",
        primary_contact_full_name="Ravi Kumar",
        primary_contact_email="ravi@example.com",
        primary_contact_phone="+919999999999",
        primary_contact_id_proof_type="passport",
    )
    group.visitors = [InvitationVisitorFactory.build(id=uuid.uuid4()) for _ in range(3)]
    unassigned = _invitation(branch.id, date(2026, 10, 10))
    db_session.add_all([group, unassigned])
    await db_session.commit()
    group_id, unassigned_id = str(group.id), str(unassigned.id)

    feed = await _feed(client, issue_token(user))
    by_id = {event["id"]: event for event in feed["events"]}

    event = by_id[group_id]
    assert set(event) == _EVENT_KEYS
    assert event["primaryContactFullName"] == "Ravi Kumar"
    assert event["visitorCount"] == 4
    assert event["hostFullName"] == "Priya Host"
    assert event["branchName"] == "Main Branch"
    assert by_id[unassigned_id]["hostId"] is None
    assert by_id[unassigned_id]["hostFullName"] is None
    assert by_id[unassigned_id]["visitorCount"] == 1


async def test_statement_count_does_not_grow_with_events(
    client: AsyncClient,
    user: User,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    """query-performance.md §2: no per-event query for host names or
    visitor counts.
    """
    await _seed_reception_role(db_session)
    branch_id = branch.id
    token = issue_token(user)
    statements: list[str] = []

    def _count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    async def _statements_for_request() -> int:
        statements.clear()
        sync_engine = db_session.bind.sync_engine  # type: ignore[union-attr]
        event.listen(sync_engine, "before_cursor_execute", _count)
        try:
            await _feed(client, token)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _count)
        return len(statements)

    host_ids = [(await _host(db_session, tenant, name=f"Host {index}")).id for index in range(9)]
    db_session.add(_invitation(branch_id, date(2026, 10, 4), host_id=host_ids[0]))
    await db_session.commit()
    few = await _statements_for_request()

    for index, host_id in enumerate(host_ids[1:]):
        invitation = _invitation(branch_id, date(2026, 10, 5 + index), host_id=host_id)
        invitation.visitors = [InvitationVisitorFactory.build(id=uuid.uuid4())]
        db_session.add(invitation)
    await db_session.commit()
    many = await _statements_for_request()

    assert many == few


# --- improve-calendar-scale-and-theme-switch: perDayLimit + paged day ---------

_DAY = "/api/v1/invitations/calendar/day"


def _busy_day(branch_id: uuid.UUID, day: date, count: int) -> list[Invitation]:
    """`count` visits on `day` spread over a few hours (with ties on time),
    names zero-padded so name order is predictable.
    """
    return [
        _invitation(
            branch_id,
            day,
            preferred_visit_time=time(9 + index % 3),
            primary_contact_full_name=f"Visitor {index:03d}",
        )
        for index in range(count)
    ]


async def _day_page(
    client: AsyncClient, token: str, day: str, **params: Any
) -> tuple[dict[str, Any], str | None]:
    response = await client.get(
        _DAY,
        params={"date": day, **params},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json(), response.headers.get("X-Calendar-Scope")


async def test_per_day_limit_keeps_each_days_first_events(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    monday = _busy_day(branch.id, date(2026, 10, 19), 25)
    tuesday = _busy_day(branch.id, date(2026, 10, 20), 4)
    db_session.add_all([*monday, *tuesday])
    await db_session.commit()
    token = issue_token(user)
    week = {"from": "2026-10-19", "to": "2026-10-25"}

    full = await _feed(client, token, week)
    limited = await _feed(client, token, {**week, "perDayLimit": 10})

    full_monday = [e["id"] for e in full["events"] if e["date"] == "2026-10-19"]
    limited_monday = [e["id"] for e in limited["events"] if e["date"] == "2026-10-19"]
    assert limited_monday == full_monday[:10]
    assert len([e for e in limited["events"] if e["date"] == "2026-10-20"]) == 4
    totals = {d["date"]: d["total"] for d in limited["days"]}
    assert totals["2026-10-19"] == 25 and totals["2026-10-20"] == 4
    assert limited["truncated"] is False

    headers = {"Authorization": f"Bearer {token}"}
    for bad in (0, 101):
        response = await client.get(_CALENDAR, params={**week, "perDayLimit": bad}, headers=headers)
        assert response.status_code == 422, (bad, response.text)


async def test_day_pages_continue_the_feed_without_gaps_or_repeats(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    db_session.add_all(_busy_day(branch.id, date(2026, 10, 19), 25))
    await db_session.commit()
    token = issue_token(user)

    feed = await _feed(client, token, {"from": "2026-10-19", "to": "2026-10-19"})
    full_order = [e["id"] for e in feed["events"]]
    first_ten = [
        e["id"]
        for e in (
            await _feed(
                client, token, {"from": "2026-10-19", "to": "2026-10-19", "perDayLimit": 10}
            )
        )["events"]
    ]

    pages: list[str] = []
    for page in (1, 2, 3):
        body, scope = await _day_page(client, token, "2026-10-19", page=page, pageSize=10)
        assert scope == "branch"
        assert body["pagination"]["total"] == 25
        assert body["pagination"]["totalPages"] == 3
        pages.extend(e["id"] for e in body["data"])
        if page == 1:
            assert [e["id"] for e in body["data"]] == first_ten

    assert pages == full_order
    assert len(set(pages)) == 25

    past_end, _ = await _day_page(client, token, "2026-10-19", page=4, pageSize=10)
    assert past_end["data"] == [] and past_end["pagination"]["total"] == 25


async def test_day_page_validation(client: AsyncClient, user: User, issue_token) -> None:
    headers = {"Authorization": f"Bearer {issue_token(user)}"}
    cases: list[dict[str, str | int]] = [
        {},
        {"date": "not-a-date"},
        {"date": "2026-10-19", "pageSize": 101},
    ]
    for params in cases:
        response = await client.get(_DAY, params=params, headers=headers)
        assert response.status_code == 422, (params, response.text)
    assert (await client.get(_DAY, params={"date": "2026-10-19"})).status_code == 401


async def test_day_page_scope_follows_the_caller(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    host = await _host(db_session, tenant)
    own = [_invitation(branch.id, date(2026, 10, 19), host_id=host.id) for _ in range(4)]
    others = _busy_day(branch.id, date(2026, 10, 19), 26)
    db_session.add_all([*own, *others])
    await db_session.commit()
    expected = _sid(*own)
    token = issue_token(host)

    body, scope = await _day_page(client, token, "2026-10-19", pageSize=50)
    assert scope == "mine"
    assert body["pagination"]["total"] == 4
    assert {e["id"] for e in body["data"]} == expected

    headers = {"Authorization": f"Bearer {token}"}
    refused = await client.get(
        _DAY, params={"date": "2026-10-19", "scope": "branch"}, headers=headers
    )
    assert refused.status_code == 403, refused.text


async def test_day_page_refuses_an_unauthorized_branch(
    client: AsyncClient,
    tenant: Tenant,
    branch: Branch,
    other_branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    reception = await _reception(db_session, tenant, branch.id)
    other_branch_id = str(other_branch.id)
    response = await client.get(
        _DAY,
        params={"date": "2026-10-19"},
        headers={
            "Authorization": f"Bearer {issue_token(reception)}",
            "X-Branch-ID": other_branch_id,
        },
    )
    assert response.status_code == 403, response.text


async def test_calendar_day_page_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch, db_session: AsyncSession
) -> None:
    db_session.add(_invitation(branch.id, date(2026, 10, 19)))
    await db_session.commit()
    criteria = CalendarCriteria(
        branch_scope="all",
        relevant_to_user_id=None,
        default_host_role_id=None,
        date_from=date(2026, 10, 19),
        date_to=date(2026, 10, 19),
        starts_at=datetime(2026, 10, 19, tzinfo=UTC),
        ends_before=datetime(2026, 10, 20, tzinfo=UTC),
        timezone="UTC",
        statuses=("approved",),
    )
    assert await InvitationRepository(db_session).calendar_day_page(criteria, offset=0, limit=10)
    other_schema = "tenant_other_test_calendar_day"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        repository = InvitationRepository(other_session)
        assert await repository.calendar_day_page(criteria, offset=0, limit=10) == []
        assert await repository.calendar_events(criteria, limit=10, per_day_limit=3) == []


async def test_ties_are_ordered_by_id_on_both_endpoints(
    client: AsyncClient, user: User, branch: Branch, db_session: AsyncSession, issue_token
) -> None:
    await _seed_reception_role(db_session)
    twins = [
        _invitation(
            branch.id,
            date(2026, 10, 19),
            preferred_visit_time=time(9),
            primary_contact_full_name="Same Name",
        )
        for _ in range(5)
    ]
    db_session.add_all(twins)
    await db_session.commit()
    expected = sorted(str(row.id) for row in twins)
    token = issue_token(user)

    feed = await _feed(client, token, {"from": "2026-10-19", "to": "2026-10-19", "perDayLimit": 5})
    body, _ = await _day_page(client, token, "2026-10-19", pageSize=5)

    assert [e["id"] for e in feed["events"]] == expected
    assert [e["id"] for e in body["data"]] == expected


async def test_paged_statement_counts_do_not_grow(
    client: AsyncClient,
    user: User,
    tenant: Tenant,
    branch: Branch,
    db_session: AsyncSession,
    issue_token,
) -> None:
    await _seed_reception_role(db_session)
    branch_id = branch.id
    token = issue_token(user)
    host_ids = [(await _host(db_session, tenant, name=f"Host {index}")).id for index in range(12)]
    statements: list[str] = []

    def _count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    async def _measure() -> tuple[int, int]:
        sync_engine = db_session.bind.sync_engine  # type: ignore[union-attr]
        event.listen(sync_engine, "before_cursor_execute", _count)
        try:
            statements.clear()
            await _feed(
                client, token, {"from": "2026-10-19", "to": "2026-10-25", "perDayLimit": 10}
            )
            feed_count = len(statements)
            statements.clear()
            await _day_page(client, token, "2026-10-19", pageSize=10)
            return feed_count, len(statements)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _count)

    db_session.add(_invitation(branch_id, date(2026, 10, 19), host_id=host_ids[0]))
    await db_session.commit()
    few = await _measure()

    for host_id in host_ids[1:]:
        invitation = _invitation(branch_id, date(2026, 10, 19), host_id=host_id)
        invitation.visitors = [InvitationVisitorFactory.build(id=uuid.uuid4())]
        db_session.add(invitation)
    await db_session.commit()
    many = await _measure()

    assert many == few
