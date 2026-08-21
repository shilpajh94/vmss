import uuid

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
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Building, Department
from vmss_api.reports.repository import BranchRollupRepository
from vmss_api.reports.service import get_cross_branch_rollup


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
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
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
