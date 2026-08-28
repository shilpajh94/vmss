import asyncio
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BuildingFactory,
    DepartmentFactory,
    FloorFactory,
    ReceptionDeskFactory,
    SecurityGateFactory,
    UserFactory,
)
from vmss_api.auth.models import User
from vmss_api.core.database import AsyncSessionLocal
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Building, Department
from vmss_api.reports import tasks
from vmss_api.reports.repository import BranchRollupRepository
from vmss_api.reports.schemas import CrossBranchRollupOut
from vmss_api.reports.service import get_cross_branch_rollup
from vmss_api.tenant.models import Tenant


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


@pytest_asyncio.fixture
async def branch_with_org_chart(
    db_session: AsyncSession, branch: Branch
) -> tuple[Building, Department]:
    """`branch` (conftest.py) gets one building, one floor, one department,
    one reception desk, and one active employee assigned to that
    department — the populated side of the rollup's per-branch counts.
    """
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id, code="ROLLUP-TWR")
    db_session.add(building)
    await db_session.flush()

    floor = FloorFactory.build(id=uuid.uuid4(), building_id=building.id, floor_number=0)
    db_session.add(floor)
    await db_session.flush()

    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=floor.id, code="ROLLUP-DEPT"
    )
    db_session.add(department)
    await db_session.flush()

    desk = ReceptionDeskFactory.build(id=uuid.uuid4(), floor_id=floor.id, code="ROLLUP-DESK")
    db_session.add(desk)

    gate = SecurityGateFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, building_id=None, code="ROLLUP-GATE"
    )
    db_session.add(gate)

    employee = UserFactory.build(
        id=uuid.uuid4(),
        email=f"employee-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        employee_code=f"EMP-{uuid.uuid4().hex[:8]}",
        department_id=department.id,
        is_active=True,
    )
    db_session.add(employee)
    await db_session.commit()
    return building, department


@pytest_asyncio.fixture
async def empty_branch(db_session: AsyncSession) -> Branch:
    """A second branch with no buildings/floors/etc. at all — proves the
    rollup reports a zero row rather than omitting a branch with nothing
    under it.
    """
    other = Branch(id=uuid.uuid4(), name="Empty Branch", code="EMPTY")
    db_session.add(other)
    await db_session.commit()
    return other


async def test_branches_rollup_success(
    client: AsyncClient,
    user: User,
    branch: Branch,
    branch_with_org_chart: tuple[Building, Department],
    empty_branch: Branch,
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/reports/branches/rollup", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()["data"]

    rows_by_code = {row["branchCode"]: row for row in body["branches"]}
    populated = rows_by_code[branch.code]
    assert populated["branchId"] == str(branch.id)
    assert populated["branchName"] == branch.name
    assert populated["buildingCount"] == 1
    assert populated["floorCount"] == 1
    assert populated["departmentCount"] == 1
    assert populated["receptionDeskCount"] == 1
    assert populated["securityGateCount"] == 1
    assert populated["activeEmployeeCount"] == 1

    empty = rows_by_code["EMPTY"]
    assert empty["branchId"] == str(empty_branch.id)
    assert empty["branchName"] == "Empty Branch"
    assert empty["buildingCount"] == 0
    assert empty["floorCount"] == 0
    assert empty["departmentCount"] == 0
    assert empty["receptionDeskCount"] == 0
    assert empty["securityGateCount"] == 0
    assert empty["activeEmployeeCount"] == 0

    assert body["totalBranches"] == 2
    assert body["totalBuildings"] == 1
    assert body["totalFloors"] == 1
    assert body["totalDepartments"] == 1
    assert body["totalReceptionDesks"] == 1
    assert body["totalSecurityGates"] == 1
    assert body["totalActiveEmployees"] == 1


async def test_branches_rollup_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/reports/branches/rollup", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_branch_rollup_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch_with_org_chart: tuple[Building, Department]
) -> None:
    """Service-level check (testing-standards.md §2/§3): a rollup computed
    against a *different* tenant schema must not see this schema's branches
    or counts at all, even though the queries here are cross-model joins
    rather than a single repository's `get()`.
    """
    other_schema = "tenant_other_test_rollup"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        rollup = await get_cross_branch_rollup(other_session)
        assert rollup.total_branches == 0
        assert rollup.branches == []

        repo = BranchRollupRepository(other_session)
        assert await repo.building_counts_by_branch() == {}


# --- Scheduled rollup-snapshot task (API-17,
# add-background-jobs-and-integration-tests) ---
#
# Every test except the retry-exhaustion one below `await`s the module's
# private async coroutines (`_send_tenant_rollup_snapshot`/
# `_dispatch_daily_rollup_snapshots`) directly, on the test's own event loop,
# against the real `tenant_acme_test` schema and real Redis
# (testing-standards.md §3's "unit-style tests still run against the real
# database" — there's no fake session substitute for the multi-query
# `get_cross_branch_rollup` call the way `invitations/tests.py` fakes a
# single `session.get()`). Going through the public Celery task (`.apply()`,
# which internally spins a *second* event loop via `asyncio.run()` — hence
# `invitations/tests.py`'s `asyncio.to_thread` wrapping) is only needed to
# exercise `self.request.retries`, so only the exhaustion test below does
# that, with the DB/email layer faked to avoid handing the shared
# `core.database.engine` connection pool between two different event loops.


class _RecordingEmailSender:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class _FailingEmailSender:
    async def send(self, **kwargs: object) -> None:
        raise RuntimeError("SMTP is down")


async def test_reports_snapshot_content_matches_on_demand_rollup(
    monkeypatch,
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    branch_with_org_chart: tuple[Building, Department],
) -> None:
    sender = _RecordingEmailSender()
    monkeypatch.setattr(tasks, "email_sender", sender)
    expected = await get_cross_branch_rollup(db_session)

    await tasks._send_tenant_rollup_snapshot(str(tenant.id), tenant.schema_name)

    assert len(sender.calls) == 1
    body = sender.calls[0]["body"]
    assert f"{expected.total_branches} branch(es)" in body
    assert f"{expected.total_buildings} building(s)" in body
    assert f"{expected.total_active_employees} active employee(s)" in body


async def test_reports_snapshot_only_admin_role_users_receive_it(
    monkeypatch, tenant: Tenant, user: User, user_without_permissions: User
) -> None:
    sender = _RecordingEmailSender()
    monkeypatch.setattr(tasks, "email_sender", sender)

    await tasks._send_tenant_rollup_snapshot(str(tenant.id), tenant.schema_name)

    recipients = {call["to"] for call in sender.calls}
    assert recipients == {user.email}


async def test_reports_snapshot_redelivered_task_does_not_send_twice(
    monkeypatch, tenant: Tenant, user: User
) -> None:
    sender = _RecordingEmailSender()
    monkeypatch.setattr(tasks, "email_sender", sender)

    await tasks._send_tenant_rollup_snapshot(str(tenant.id), tenant.schema_name)
    await tasks._send_tenant_rollup_snapshot(str(tenant.id), tenant.schema_name)

    assert len(sender.calls) == 1


async def test_reports_snapshot_no_admin_recipients_logs_info_and_sends_nothing(
    monkeypatch, tenant: Tenant
) -> None:
    sender = _RecordingEmailSender()
    monkeypatch.setattr(tasks, "email_sender", sender)
    logged_info = []
    monkeypatch.setattr(tasks.logger, "info", lambda event, **kw: logged_info.append((event, kw)))

    await tasks._send_tenant_rollup_snapshot(str(tenant.id), tenant.schema_name)

    assert sender.calls == []
    assert logged_info and logged_info[0][0] == "reports_snapshot_no_admin_recipients"


async def test_reports_snapshot_retry_exhaustion_logs_error_with_tenant_context(
    monkeypatch,
) -> None:
    tenant_id = str(uuid.uuid4())
    empty_rollup = CrossBranchRollupOut(
        branches=[],
        total_branches=0,
        total_buildings=0,
        total_floors=0,
        total_departments=0,
        total_reception_desks=0,
        total_security_gates=0,
        total_active_employees=0,
    )

    @asynccontextmanager
    async def _fake_tenant_session_scope(schema_name: str):
        yield object()  # never touched — service/repository below are faked

    class _FakeAdminUser:
        email = "admin@acme-test.example"

    class _FakeBranchRollupRepository:
        def __init__(self, session: object) -> None:
            pass

        async def admin_users(self) -> list[_FakeAdminUser]:
            return [_FakeAdminUser()]

    async def _fake_get_cross_branch_rollup(session: object) -> CrossBranchRollupOut:
        return empty_rollup

    monkeypatch.setattr(tasks, "tenant_session_scope", _fake_tenant_session_scope)
    monkeypatch.setattr(tasks.service, "get_cross_branch_rollup", _fake_get_cross_branch_rollup)
    monkeypatch.setattr(tasks, "BranchRollupRepository", _FakeBranchRollupRepository)
    monkeypatch.setattr(tasks, "email_sender", _FailingEmailSender())
    logged_error = []
    monkeypatch.setattr(tasks.logger, "error", lambda event, **kw: logged_error.append((event, kw)))
    # `max_retries=0` — the first failure is already "exhausted", so
    # `.apply()` hits the exhaustion branch immediately instead of actually
    # sleeping through `retry_backoff`'s delay (same trick
    # `invitations/tests.py::test_send_visit_confirmation_exhausted_retries_logs_error`
    # uses).
    monkeypatch.setattr(tasks.send_tenant_rollup_snapshot, "max_retries", 0)

    result = await asyncio.to_thread(
        tasks.send_tenant_rollup_snapshot.apply,
        kwargs={"tenant_id": tenant_id, "tenant_schema": "tenant_acme_test"},
    )

    assert result.failed()
    assert logged_error and logged_error[0][0] == "reports_snapshot_dispatch_exhausted"
    assert logged_error[0][1]["tenant_id"] == tenant_id


async def test_dispatch_daily_rollup_snapshots_enqueues_every_active_tenant(
    monkeypatch, tenant: Tenant, make_tenant_schema
) -> None:
    """One tenant's `.delay()` raising must not stop the dispatcher from
    still enqueueing every other active tenant in the same run
    (`background-jobs` capability's scheduled-task isolation requirement).
    """
    second_schema = "tenant_other_test_snapshot_dispatch"
    await make_tenant_schema(second_schema)
    second_tenant = Tenant(
        id=uuid.uuid4(),
        name="Second Co",
        slug=f"second-{uuid.uuid4().hex[:8]}",
        schema_name=second_schema,
    )
    async with AsyncSessionLocal() as global_session:
        global_session.add(second_tenant)
        await global_session.commit()

    enqueued: list[str] = []

    def _fake_delay(*, tenant_id: str, tenant_schema: str) -> None:
        if tenant_id == str(tenant.id):
            raise RuntimeError("broker hiccup")
        enqueued.append(tenant_id)

    monkeypatch.setattr(tasks.send_tenant_rollup_snapshot, "delay", _fake_delay)

    await tasks._dispatch_daily_rollup_snapshots()

    assert str(second_tenant.id) in enqueued
    assert str(tenant.id) not in enqueued
