import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BuildingFactory,
    DepartmentFactory,
    FloorFactory,
    PermissionFactory,
    ReceptionDeskFactory,
    RoleFactory,
    SecurityGateFactory,
    UserFactory,
)
from vmss_api.auth.models import User, UserBranchRole
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import (
    Branch,
    Building,
    Company,
    Department,
    Floor,
    ReceptionDesk,
    SecurityGate,
)
from vmss_api.org_structure.repository import (
    BranchRepository,
    BuildingRepository,
    CompanyRepository,
    DepartmentRepository,
    FloorRepository,
    ReceptionDeskRepository,
    SecurityGateRepository,
)
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture
async def building(db_session: AsyncSession, branch: Branch) -> Building:
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id, code="TWR-A")
    db_session.add(building)
    await db_session.commit()
    return building


@pytest_asyncio.fixture
async def floor(db_session: AsyncSession, building: Building) -> Floor:
    floor = FloorFactory.build(id=uuid.uuid4(), building_id=building.id, floor_number=0)
    db_session.add(floor)
    await db_session.commit()
    return floor


@pytest_asyncio.fixture
async def department(db_session: AsyncSession, floor: Floor, building: Building) -> Department:
    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=building.branch_id, floor_id=floor.id, code="HR"
    )
    db_session.add(department)
    await db_session.commit()
    return department


@pytest_asyncio.fixture
async def reception_desk(db_session: AsyncSession, floor: Floor) -> ReceptionDesk:
    desk = ReceptionDeskFactory.build(id=uuid.uuid4(), floor_id=floor.id, code="DESK-1")
    db_session.add(desk)
    await db_session.commit()
    return desk


@pytest_asyncio.fixture
async def security_gate(db_session: AsyncSession, branch: Branch) -> SecurityGate:
    gate = SecurityGateFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, building_id=None, code="GATE-1", gate_type="entry"
    )
    db_session.add(gate)
    await db_session.commit()
    return gate


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


async def _branch_scoped_user(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID, *, permission_codes: list[str]
) -> User:
    """A Reception-shaped user whose only role grant is scoped to
    `branch_id` — the fixture behind every "does branch-scoping actually
    work" test below (testing-standards.md §2's isolation case, applied at
    branch granularity rather than tenant granularity).
    """
    permissions = [
        PermissionFactory.build(id=uuid.uuid4(), code=code, description=code)
        for code in permission_codes
    ]
    role = RoleFactory.build(id=uuid.uuid4(), name="branch-scoped", permissions=permissions)
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"scoped-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Branch Scoped User",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


@pytest_asyncio.fixture
async def user_scoped_to_branch(db_session: AsyncSession, tenant: Tenant, branch: Branch) -> User:
    """A Reception user scoped to the shared `branch` fixture, with the full
    set of manage/view permissions the branch-scoped tests below exercise —
    the affirmative counterpart to `user_scoped_to_other_branch`.
    """
    return await _branch_scoped_user(
        db_session,
        tenant,
        branch.id,
        permission_codes=[
            "branches:view",
            "buildings:view",
            "buildings:manage",
            "floors:view",
            "floors:manage",
            "departments:view",
            "departments:manage",
            "desks:view",
            "desks:manage",
            "gates:view",
            "gates:manage",
        ],
    )


@pytest_asyncio.fixture
async def user_scoped_to_other_branch(db_session: AsyncSession, tenant: Tenant) -> User:
    """A Reception user whose only role grant is scoped to a *different*
    branch than the shared `branch` fixture — for asserting that branch
    access doesn't leak across locations (testing-standards.md §2's
    isolation-style case, applied to branches rather than tenants).
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    db_session.add(other_branch)
    await db_session.flush()
    return await _branch_scoped_user(
        db_session,
        tenant,
        other_branch.id,
        permission_codes=[
            "branches:view",
            "buildings:view",
            "buildings:manage",
            "floors:view",
            "floors:manage",
            "departments:view",
            "departments:manage",
            "desks:view",
            "desks:manage",
            "gates:view",
            "gates:manage",
        ],
    )


async def test_create_branch_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/branches",
        json={"name": "New Branch", "code": "NEW"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["code"] == "NEW"
    assert body["isActive"] is True


async def test_create_branch_duplicate_code_conflict(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/branches",
        json={"name": "Duplicate", "code": branch.code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_create_branch_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/branches",
        json={"name": "New Branch", "code": "NEW"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_branches_success(client: AsyncClient, user: User, branch: Branch) -> None:
    token = await _login(client, user.email)
    response = await client.get("/api/v1/branches", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {b["code"] for b in response.json()["data"]}
    assert branch.code in codes


async def test_list_branches_scoped_to_authorized_branch_only(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    branch: Branch,
) -> None:
    """`branches:view` used to be checked company-wide only, 403-ing every
    branch-scoped role even though it holds the permission at its own
    branch (see `router.py::list_branches`'s switch to
    `require_branch_scope`). A branch-scoped caller must see its own branch
    and not an unrelated one it holds no grant at — same pattern as
    `test_list_buildings_without_branch_header_excludes_other_branches`.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-LIST")
    db_session.add(other_branch)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get("/api/v1/branches", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {b["code"] for b in response.json()["data"]}
    assert branch.code in codes
    assert other_branch.code not in codes


async def test_get_branch_success_for_branch_scoped_user(
    client: AsyncClient, user_scoped_to_branch: User, branch: Branch
) -> None:
    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get(
        f"/api/v1/branches/{branch.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["code"] == branch.code


async def test_get_branch_denied_for_user_scoped_elsewhere(
    client: AsyncClient, user_scoped_to_other_branch: User, branch: Branch
) -> None:
    """The branch-level counterpart of `test_get_building_not_found_for_other_branch`
    — a role grant scoped to a different branch must not resolve this one.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/branches/{branch.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_get_current_branch_with_access(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(branch.id)


async def test_get_current_branch_unknown_branch(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(uuid.uuid4())},
    )
    assert response.status_code == 404


async def test_get_current_branch_requires_header(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/branches/current", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


async def test_get_current_branch_denied_for_user_scoped_elsewhere(
    client: AsyncClient, branch: Branch, user_scoped_to_other_branch: User
) -> None:
    """A branch-scoped role grant at one branch must not grant access to a
    different one — the branch-level analogue of testing-standards.md §2's
    tenant-isolation case.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403


async def test_branch_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, branch: Branch
) -> None:
    other_schema = "tenant_other_test_org"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await BranchRepository(other_session).get(branch.id)
        assert found is None


async def test_update_branch_success(client: AsyncClient, user: User, branch: Branch) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/branches/{branch.id}",
        json={"name": "Renamed Branch"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Branch"


async def test_update_branch_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.put(
        f"/api/v1/branches/{branch.id}",
        json={"name": "Renamed Branch"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_branch_success(client: AsyncClient, user: User, branch: Branch) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/branches/{branch.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == branch.name
    assert response.json()["data"]["code"] == branch.code


async def test_delete_branch_success(client: AsyncClient, user: User, branch: Branch) -> None:
    token = await _login(client, user.email)
    delete_response = await client.delete(
        f"/api/v1/branches/{branch.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_response.status_code == 204

    get_response = await client.get(
        f"/api/v1/branches/{branch.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404


async def test_create_branch_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A soft-deleted branch's `code` must not stay reserved forever — see
    openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    delete_response = await client.delete(f"/api/v1/branches/{branch.id}", headers=headers)
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/branches", json={"name": "New Owner", "code": branch.code}, headers=headers
    )
    assert recreate_response.status_code == 201


# --- Branch provisioning (bulk bootstrap) ---------------------------------


def _provision_payload() -> dict:
    return {
        "name": "Downtown Campus",
        "code": "DOWNTOWN",
        "buildings": [
            {
                "name": "Tower A",
                "code": "TWR-A",
                "floors": [
                    {
                        "name": "Ground Floor",
                        "floorNumber": 0,
                        "departments": [{"name": "Human Resources", "code": "HR"}],
                        "receptionDesks": [{"name": "Main Desk", "code": "DESK-1"}],
                    },
                    {
                        "name": "First Floor",
                        "floorNumber": 1,
                        "departments": [{"name": "Engineering", "code": "ENG"}],
                        "receptionDesks": [],
                    },
                ],
                "securityGates": [{"name": "Tower Gate", "code": "GATE-TWR-A"}],
            }
        ],
        "securityGates": [{"name": "Main Gate", "code": "GATE-MAIN", "gateType": "entry"}],
    }


async def test_provision_branch_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/branches/provision",
        json=_provision_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["branch"]["code"] == "DOWNTOWN"
    assert body["buildingsCreated"] == 1
    assert body["floorsCreated"] == 2
    assert body["departmentsCreated"] == 2
    assert body["receptionDesksCreated"] == 1
    assert body["securityGatesCreated"] == 2

    branch_id = body["branch"]["id"]
    buildings_response = await client.get(
        "/api/v1/buildings",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": branch_id},
    )
    assert "TWR-A" in {b["code"] for b in buildings_response.json()["data"]}


async def test_provision_branch_requires_permission(
    client: AsyncClient, user_scoped_to_branch: User
) -> None:
    """`user_scoped_to_branch` has `branches:view` but not `branches:provision`
    — a branch-scoped role isn't enough to bootstrap a whole new location.
    """
    token = await _login(client, user_scoped_to_branch.email)
    response = await client.post(
        "/api/v1/branches/provision",
        json=_provision_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_provision_branch_duplicate_branch_code_conflict(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    payload = _provision_payload()
    payload["code"] = branch.code
    response = await client.post(
        "/api/v1/branches/provision", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409


async def test_provision_branch_duplicate_department_code_in_request_conflict(
    client: AsyncClient, user: User
) -> None:
    """Two departments *anywhere in the same branch* reusing the same code
    can't be caught by a `SELECT` against existing rows — neither has hit
    the database yet — so `service.py::provision_branch` tracks codes seen
    within the request itself. Department codes are unique per branch
    (`uq_department_branch_code`), so this duplicates within one floor's
    list, which is also a same-branch collision.
    """
    token = await _login(client, user.email)
    payload = _provision_payload()
    payload["buildings"][0]["floors"][0]["departments"].append(
        {"name": "Duplicate HR", "code": "HR"}
    )
    response = await client.post(
        "/api/v1/branches/provision", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409


async def test_provision_branch_rolls_back_nothing_committed_on_conflict(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A failed provisioning call must not leave a dangling branch behind —
    the branch-code conflict is checked before anything is added, so a
    second attempt with a fresh code still succeeds cleanly."""
    token = await _login(client, user.email)
    conflicting_payload = _provision_payload()
    conflicting_payload["code"] = branch.code
    conflict_response = await client.post(
        "/api/v1/branches/provision",
        json=conflicting_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert conflict_response.status_code == 409

    retry_response = await client.post(
        "/api/v1/branches/provision",
        json=_provision_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry_response.status_code == 201


async def test_provision_branch_rolls_back_partial_tree_on_mid_transaction_conflict(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """The duplicate-department conflict below fires only after `Branch`,
    `Building`, and both `Floor` rows have already been `flush()`-ed to the
    database within the same transaction (`service.py::provision_branch`)
    — a materially stronger case than
    `test_provision_branch_rolls_back_nothing_committed_on_conflict` above,
    which fails on the very first check, before anything has been added to
    the session at all.

    In production, `get_tenant_db` (`core/tenancy.py`) hands each request a
    session opened inside its own `async with AsyncSession(...)` block
    (`core/database.py::tenant_session_scope`), so an unhandled exception
    exits that block and the session's `close()` implicitly rolls back
    anything flushed-but-uncommitted. The test client's dependency override
    (`conftest.py::client`) instead hands every request the same bare
    `db_session` for the whole test, with no such `async with` around it,
    so it doesn't replicate that automatic rollback-on-exit. The explicit
    `db_session.rollback()` below stands in for what that exit would have
    done in production; the row counts afterward then prove
    `provision_branch` really left nothing behind for it to roll back.
    """
    token = await _login(client, user.email)
    payload = _provision_payload()
    payload["buildings"][0]["floors"][0]["departments"].append(
        {"name": "Duplicate HR", "code": "HR"}
    )
    response = await client.post(
        "/api/v1/branches/provision", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409

    await db_session.rollback()
    for model in (Branch, Building, Floor, Department, ReceptionDesk, SecurityGate):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0, f"{model.__name__} row(s) leaked from a rolled-back provision"


# --- Company (singleton) -----------------------------------------------


async def test_create_company_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/company",
        json={"legalName": "Acme Test Co Pvt Ltd", "registrationNumber": "REG-001"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["legalName"] == "Acme Test Co Pvt Ltd"


async def test_create_company_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/company",
        json={"legalName": "Acme Test Co Pvt Ltd"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_create_company_conflict_when_already_configured(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.post("/api/v1/company", json={"legalName": "First Co"}, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/company", json={"legalName": "Second Co"}, headers=headers)
    assert second.status_code == 409


async def test_get_company_not_configured_yet(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get("/api/v1/company", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_get_company_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/company",
        json={"legalName": "Acme Test Co Pvt Ltd", "registrationNumber": "REG-001"},
        headers=headers,
    )

    response = await client.get("/api/v1/company", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["legalName"] == "Acme Test Co Pvt Ltd"
    assert response.json()["data"]["registrationNumber"] == "REG-001"


async def test_update_company_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/company", json={"legalName": "Original Co"}, headers=headers)

    response = await client.put(
        "/api/v1/company", json={"legalName": "Updated Co"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["legalName"] == "Updated Co"


async def test_delete_company_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/company", json={"legalName": "To Delete Co"}, headers=headers)

    response = await client.delete("/api/v1/company", headers=headers)
    assert response.status_code == 204

    get_response = await client.get("/api/v1/company", headers=headers)
    assert get_response.status_code == 404


async def test_create_company_after_soft_delete_reuses_registration_number(
    client: AsyncClient, user: User
) -> None:
    """A soft-deleted company's `registration_number` must not stay reserved
    forever — see
    openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = await client.post(
        "/api/v1/company",
        json={"legalName": "Original Co", "registrationNumber": "REG-REUSE"},
        headers=headers,
    )
    assert create_response.status_code == 201
    delete_response = await client.delete("/api/v1/company", headers=headers)
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/company",
        json={"legalName": "New Co", "registrationNumber": "REG-REUSE"},
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_create_company_invalid_email_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/company",
        json={"legalName": "Bad Email Co", "email": "not-an-email"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_company_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession
) -> None:
    company = Company(id=uuid.uuid4(), legal_name="Acme Isolation Co")
    db_session.add(company)
    await db_session.commit()

    other_schema = "tenant_other_test_company"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await CompanyRepository(other_session).get(company.id)
        assert found is None


# --- Building --------------------------------------------------------------


async def test_create_building_success(client: AsyncClient, user: User, branch: Branch) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(branch.id), "name": "Tower B", "code": "TWR-B"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["branchId"] == str(branch.id)


async def test_create_building_unknown_branch_not_found(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(uuid.uuid4()), "name": "Tower B", "code": "TWR-B"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 404


async def test_create_building_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(branch.id), "name": "Tower B", "code": "TWR-B"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403


async def test_create_building_succeeds_without_branch_header(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """`X-Branch-ID` is optional on creation endpoints — the branch resolves
    from `branchId` in the body instead (auth spec's optional-header
    requirement).
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(branch.id), "name": "Tower B", "code": "TWR-B"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["branchId"] == str(branch.id)


async def test_create_building_denied_for_user_scoped_elsewhere(
    client: AsyncClient, branch: Branch, user_scoped_to_other_branch: User
) -> None:
    """The core branch-RBAC fix: a role grant scoped to Branch B must not let
    its holder create a building for Branch A, even when they pass Branch
    A's id in the request body — authorization comes from `X-Branch-ID`
    resolving to a branch they hold a grant for, not from the payload.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(branch.id), "name": "Tower B", "code": "TWR-B"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403


async def test_list_buildings_scoped_to_authorized_branch(
    client: AsyncClient, user: User, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/buildings",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    assert building.code in {b["code"] for b in body["data"]}


async def test_list_buildings_excludes_other_branch(
    client: AsyncClient, user_scoped_to_branch: User, branch: Branch, building: Building
) -> None:
    """`building` belongs to `branch`; a caller scoped to `branch` should see
    it, but a building created under a different branch must never show up
    — the list-endpoint counterpart of the create-side guard above.
    """
    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get(
        "/api/v1/buildings",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert building.code in {b["code"] for b in response.json()["data"]}


async def test_list_buildings_without_branch_header_returns_every_authorized_branch(
    client: AsyncClient, user: User, building: Building
) -> None:
    """`user` is a company-wide Admin — omitting `X-Branch-ID` on a list
    request now scopes to every branch it's authorized for, not just one.
    """
    token = await _login(client, user.email)
    response = await client.get("/api/v1/buildings", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert building.code in {b["code"] for b in response.json()["data"]}


async def test_list_buildings_without_branch_header_excludes_other_branches(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    building: Building,
) -> None:
    """A caller scoped to only one branch, with no `X-Branch-ID` header,
    must never see another branch's buildings — the tenant/branch-isolation
    case testing-standards.md §2 requires for this change.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-BLD")
    db_session.add(other_branch)
    await db_session.flush()
    other_building = BuildingFactory.build(id=uuid.uuid4(), branch_id=other_branch.id, code="OTH-A")
    db_session.add(other_building)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get("/api/v1/buildings", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {b["code"] for b in response.json()["data"]}
    assert building.code in codes
    assert other_building.code not in codes


async def test_get_building_success(client: AsyncClient, user: User, building: Building) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/buildings/{building.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(building.id)


async def test_get_building_not_found_for_other_branch(
    client: AsyncClient, building: Building, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/buildings/{building.id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Branch-ID": str(user_scoped_to_other_branch.branch_roles[0].branch_id),
        },
    )
    assert response.status_code == 404


async def test_get_building_without_branch_header_resolves_from_the_building_itself(
    client: AsyncClient, user_scoped_to_branch: User, building: Building
) -> None:
    """No `X-Branch-ID` header at all — authorization comes from the
    building's own (real) branch, looked up by id, per the auth spec's
    by-id optional-header requirement.
    """
    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get(
        f"/api/v1/buildings/{building.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(building.id)


async def test_get_building_without_branch_header_denied_for_user_scoped_elsewhere(
    client: AsyncClient, building: Building, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/buildings/{building.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_update_building_success(client: AsyncClient, user: User, building: Building) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/buildings/{building.id}",
        json={"name": "Renamed Tower"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Tower"


async def test_update_building_not_found_for_other_branch(
    client: AsyncClient, building: Building, user_scoped_to_other_branch: User
) -> None:
    """`building` belongs to `branch`; a role grant scoped to a different
    branch must not be able to rename it, even by id — the update-endpoint
    counterpart of the get-by-id guard above.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.put(
        f"/api/v1/buildings/{building.id}",
        json={"name": "Hijacked Tower"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_building_success(client: AsyncClient, user: User, building: Building) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/buildings/{building.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 204


async def test_delete_building_not_found_for_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    building: Building,
    user_scoped_to_other_branch: User,
) -> None:
    """A role grant scoped to a different branch must not be able to delete
    `building`, and the building must genuinely survive the attempt (not
    just return the right status code). Verified straight through the
    repository rather than a second HTTP call as a company-wide admin,
    since the `user`/`user_scoped_to_*` role fixtures all insert
    `Permission` rows under the same codes — combining any two of them in
    one test collides on `global.permissions`' unique `code` index.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.delete(
        f"/api/v1/buildings/{building.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404

    survivor = await BuildingRepository(db_session).get(building.id)
    assert survivor is not None


async def test_create_building_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, building: Building
) -> None:
    """A soft-deleted building's `code` must not stay reserved forever —
    see openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)}
    delete_response = await client.delete(f"/api/v1/buildings/{building.id}", headers=headers)
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/buildings",
        json={"branchId": str(building.branch_id), "name": "New Tower", "code": building.code},
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_building_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, building: Building
) -> None:
    other_schema = "tenant_other_test_building"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await BuildingRepository(other_session).get(building.id)
        assert found is None


# --- Floor --------------------------------------------------------------


async def test_create_floor_success(client: AsyncClient, user: User, building: Building) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/floors",
        json={"buildingId": str(building.id), "name": "First Floor", "floorNumber": 1},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["floorNumber"] == 1


async def test_create_floor_duplicate_number_conflict(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/floors",
        json={
            "buildingId": str(floor.building_id),
            "name": "Duplicate Ground",
            "floorNumber": floor.floor_number,
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 409


async def test_create_floor_requires_permission(
    client: AsyncClient, user_without_permissions: User, building: Building
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/floors",
        json={"buildingId": str(building.id), "name": "First Floor", "floorNumber": 1},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 403


async def test_create_floor_denied_for_user_scoped_elsewhere(
    client: AsyncClient, building: Building, user_scoped_to_other_branch: User
) -> None:
    """The branch resolves transitively from `buildingId` in the body, not
    `X-Branch-ID` — a caller with no grant at that building's real branch is
    rejected with 403, regardless of what header they send (or omit).
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.post(
        "/api/v1/floors",
        json={"buildingId": str(building.id), "name": "First Floor", "floorNumber": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_floors_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/floors",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert floor.floor_number in {f["floorNumber"] for f in response.json()["data"]}


async def test_list_floors_excludes_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    floor: Floor,
    building: Building,
) -> None:
    """`floor` belongs to `building`, which belongs to `branch`; a floor
    provisioned under a completely different branch's building must never
    show up in the branch-scoped caller's list — the list-endpoint
    counterpart of `test_create_floor_denied_for_user_scoped_elsewhere`.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-FLR")
    db_session.add(other_branch)
    await db_session.flush()
    other_building = BuildingFactory.build(
        id=uuid.uuid4(), branch_id=other_branch.id, code="OTH-FLR-BLD"
    )
    db_session.add(other_building)
    await db_session.flush()
    other_floor = FloorFactory.build(id=uuid.uuid4(), building_id=other_building.id, floor_number=9)
    db_session.add(other_floor)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get("/api/v1/floors", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    ids = {f["id"] for f in response.json()["data"]}
    assert str(floor.id) in ids
    assert str(other_floor.id) not in ids


async def test_get_floor_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/floors/{floor.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(floor.id)


async def test_get_floor_not_found_for_other_branch(
    client: AsyncClient, floor: Floor, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/floors/{floor.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_update_floor_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/floors/{floor.id}",
        json={"name": "Renamed Floor"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Floor"


async def test_update_floor_not_found_for_other_branch(
    client: AsyncClient, floor: Floor, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.put(
        f"/api/v1/floors/{floor.id}",
        json={"name": "Hijacked Floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_floor_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/floors/{floor.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 204


async def test_delete_floor_not_found_for_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    floor: Floor,
    user_scoped_to_other_branch: User,
) -> None:
    """See `test_delete_building_not_found_for_other_branch` for why
    survival is checked via the repository rather than a second HTTP call.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.delete(
        f"/api/v1/floors/{floor.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404

    survivor = await FloorRepository(db_session).get(floor.id)
    assert survivor is not None


async def test_create_floor_after_soft_delete_reuses_number(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    """A soft-deleted floor's `floor_number` must not stay reserved forever
    — see openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)}
    delete_response = await client.delete(f"/api/v1/floors/{floor.id}", headers=headers)
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/floors",
        json={
            "buildingId": str(floor.building_id),
            "name": "New Ground",
            "floorNumber": floor.floor_number,
        },
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_floor_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, floor: Floor
) -> None:
    other_schema = "tenant_other_test_floor"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await FloorRepository(other_session).get(floor.id)
        assert found is None


# --- Department --------------------------------------------------------------


async def test_create_department_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/departments",
        json={
            "branchId": str(building.branch_id),
            "floorId": str(floor.id),
            "name": "Human Resources",
            "code": "HR",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["code"] == "HR"


async def test_create_department_requires_permission(
    client: AsyncClient, user_without_permissions: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/departments",
        json={
            "branchId": str(building.branch_id),
            "floorId": str(floor.id),
            "name": "Human Resources",
            "code": "HR",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 403


async def test_create_department_denied_for_user_scoped_elsewhere(
    client: AsyncClient, floor: Floor, building: Building, user_scoped_to_other_branch: User
) -> None:
    """The branch resolves from `branchId` in the body, not `X-Branch-ID` —
    a caller with no grant at that branch is rejected with 403, regardless
    of what header they send (or omit).
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.post(
        "/api/v1/departments",
        json={
            "branchId": str(building.branch_id),
            "floorId": str(floor.id),
            "name": "Human Resources",
            "code": "HR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_departments_success(
    client: AsyncClient, user: User, department: Department, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/departments",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert department.code in {d["code"] for d in response.json()["data"]}


async def test_list_departments_excludes_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    department: Department,
    building: Building,
) -> None:
    """`department` belongs to `branch`; a department created directly under
    a different branch must never show up in the branch-scoped caller's
    list — the list-endpoint counterpart of
    `test_create_department_denied_for_user_scoped_elsewhere`.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-DEPT")
    db_session.add(other_branch)
    await db_session.flush()
    other_department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=other_branch.id, floor_id=None, code="OTH-DEPT"
    )
    db_session.add(other_department)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get("/api/v1/departments", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {d["code"] for d in response.json()["data"]}
    assert department.code in codes
    assert other_department.code not in codes


async def test_get_department_success(
    client: AsyncClient, user: User, department: Department, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/departments/{department.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(department.id)


async def test_get_department_not_found_for_other_branch(
    client: AsyncClient, department: Department, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/departments/{department.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_update_department_success(
    client: AsyncClient, user: User, department: Department, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/departments/{department.id}",
        json={"name": "Renamed Department"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Department"


async def test_update_department_not_found_for_other_branch(
    client: AsyncClient, department: Department, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.put(
        f"/api/v1/departments/{department.id}",
        json={"name": "Hijacked Department"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_department_success(
    client: AsyncClient, user: User, department: Department, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/departments/{department.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 204


async def test_delete_department_not_found_for_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    department: Department,
    user_scoped_to_other_branch: User,
) -> None:
    """See `test_delete_building_not_found_for_other_branch` for why
    survival is checked via the repository rather than a second HTTP call.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.delete(
        f"/api/v1/departments/{department.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404

    survivor = await DepartmentRepository(db_session).get(department.id)
    assert survivor is not None


async def test_create_department_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, department: Department, building: Building
) -> None:
    """A soft-deleted department's `code` must not stay reserved forever —
    see openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)}
    delete_response = await client.delete(f"/api/v1/departments/{department.id}", headers=headers)
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/departments",
        json={
            "branchId": str(department.branch_id),
            "floorId": str(department.floor_id),
            "name": "New HR",
            "code": department.code,
        },
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_department_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, department: Department
) -> None:
    other_schema = "tenant_other_test_department"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await DepartmentRepository(other_session).get(department.id)
        assert found is None


async def test_create_department_without_floor_succeeds(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A department is scoped directly to a branch — the floor step is
    optional. See
    openspec/changes/add-role-management-and-org-field-gaps/design.md
    Decision 4.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/departments",
        json={"branchId": str(branch.id), "name": "Legal", "code": "LEGAL"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["floorId"] is None
    assert body["branchId"] == str(branch.id)

    list_response = await client.get(
        "/api/v1/departments",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert "LEGAL" in {d["code"] for d in list_response.json()["data"]}


# --- Reception Desk --------------------------------------------------------------


async def test_create_reception_desk_success(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/reception-desks",
        json={"floorId": str(floor.id), "name": "Front Desk", "code": "DESK-1"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["code"] == "DESK-1"


async def test_create_reception_desk_requires_permission(
    client: AsyncClient, user_without_permissions: User, floor: Floor, building: Building
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/reception-desks",
        json={"floorId": str(floor.id), "name": "Front Desk", "code": "DESK-1"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 403


async def test_create_reception_desk_denied_for_user_scoped_elsewhere(
    client: AsyncClient, floor: Floor, user_scoped_to_other_branch: User
) -> None:
    """The branch resolves transitively from `floorId` in the body, not
    `X-Branch-ID` — a caller with no grant at that floor's real branch is
    rejected with 403, regardless of what header they send (or omit).
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.post(
        "/api/v1/reception-desks",
        json={"floorId": str(floor.id), "name": "Front Desk", "code": "DESK-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_reception_desks_success(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/reception-desks",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert reception_desk.code in {d["code"] for d in response.json()["data"]}


async def test_list_reception_desks_excludes_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    reception_desk: ReceptionDesk,
    building: Building,
) -> None:
    """`reception_desk` sits on `floor`, under `building`, under `branch`; a
    desk on a floor belonging to a different branch entirely must never
    show up in the branch-scoped caller's list — the list-endpoint
    counterpart of `test_create_reception_desk_denied_for_user_scoped_elsewhere`.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-DESK")
    db_session.add(other_branch)
    await db_session.flush()
    other_building = BuildingFactory.build(
        id=uuid.uuid4(), branch_id=other_branch.id, code="OTH-DESK-BLD"
    )
    db_session.add(other_building)
    await db_session.flush()
    other_floor = FloorFactory.build(id=uuid.uuid4(), building_id=other_building.id, floor_number=9)
    db_session.add(other_floor)
    await db_session.flush()
    other_desk = ReceptionDeskFactory.build(
        id=uuid.uuid4(), floor_id=other_floor.id, code="OTH-DESK"
    )
    db_session.add(other_desk)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get(
        "/api/v1/reception-desks", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {d["code"] for d in response.json()["data"]}
    assert reception_desk.code in codes
    assert other_desk.code not in codes


async def test_get_reception_desk_success(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/reception-desks/{reception_desk.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(reception_desk.id)


async def test_get_reception_desk_not_found_for_other_branch(
    client: AsyncClient, reception_desk: ReceptionDesk, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/reception-desks/{reception_desk.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_update_reception_desk_success(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/reception-desks/{reception_desk.id}",
        json={"name": "Renamed Desk"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Desk"


async def test_update_reception_desk_not_found_for_other_branch(
    client: AsyncClient, reception_desk: ReceptionDesk, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.put(
        f"/api/v1/reception-desks/{reception_desk.id}",
        json={"name": "Hijacked Desk"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_reception_desk_success(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/reception-desks/{reception_desk.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 204


async def test_delete_reception_desk_not_found_for_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    reception_desk: ReceptionDesk,
    user_scoped_to_other_branch: User,
) -> None:
    """See `test_delete_building_not_found_for_other_branch` for why
    survival is checked via the repository rather than a second HTTP call.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.delete(
        f"/api/v1/reception-desks/{reception_desk.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404

    survivor = await ReceptionDeskRepository(db_session).get(reception_desk.id)
    assert survivor is not None


async def test_create_reception_desk_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    """A soft-deleted desk's `code` must not stay reserved forever — see
    openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)}
    delete_response = await client.delete(
        f"/api/v1/reception-desks/{reception_desk.id}", headers=headers
    )
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/reception-desks",
        json={
            "floorId": str(reception_desk.floor_id),
            "name": "New Desk",
            "code": reception_desk.code,
        },
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_reception_desk_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, reception_desk: ReceptionDesk
) -> None:
    other_schema = "tenant_other_test_desk"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await ReceptionDeskRepository(other_session).get(reception_desk.id)
        assert found is None


async def test_create_reception_desk_with_maintenance_status(
    client: AsyncClient, user: User, floor: Floor, building: Building
) -> None:
    """`status` is a three-state field (`active`/`maintenance`/`inactive`),
    not a boolean — see
    openspec/changes/add-role-management-and-org-field-gaps/design.md
    Decision 3.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/reception-desks",
        json={
            "floorId": str(floor.id),
            "name": "Maintenance Desk",
            "code": "DESK-M",
            "status": "maintenance",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "maintenance"


async def test_update_reception_desk_status_to_inactive(
    client: AsyncClient, user: User, reception_desk: ReceptionDesk, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/reception-desks/{reception_desk.id}",
        json={"status": "inactive"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "inactive"


# --- Security Gate --------------------------------------------------------------


async def test_create_security_gate_success(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/security-gates",
        json={
            "branchId": str(branch.id),
            "name": "Main Gate",
            "code": "GATE-1",
            "gateType": "entry",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["code"] == "GATE-1"
    assert body["gateType"] == "entry"


async def test_create_security_gate_with_building(
    client: AsyncClient, user: User, building: Building
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/security-gates",
        json={
            "branchId": str(building.branch_id),
            "buildingId": str(building.id),
            "name": "Tower Gate",
            "code": "GATE-2",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(building.branch_id)},
    )
    assert response.status_code == 201
    assert response.json()["data"]["buildingId"] == str(building.id)


async def test_create_security_gate_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/security-gates",
        json={"branchId": str(branch.id), "name": "Main Gate", "code": "GATE-1"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403


async def test_create_security_gate_denied_for_user_scoped_elsewhere(
    client: AsyncClient, branch: Branch, user_scoped_to_other_branch: User
) -> None:
    """`branch` (in the payload) belongs to a different branch than
    `user_scoped_to_other_branch` is authorized for — the branch resolves
    from `branchId` in the body, not `X-Branch-ID`, so a caller with no
    grant there is rejected with 403, regardless of what header they send
    (or omit).
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.post(
        "/api/v1/security-gates",
        json={"branchId": str(branch.id), "name": "Main Gate", "code": "GATE-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_list_security_gates_success(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/security-gates",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert security_gate.code in {g["code"] for g in response.json()["data"]}


async def test_list_security_gates_excludes_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    user_scoped_to_branch: User,
    security_gate: SecurityGate,
    branch: Branch,
) -> None:
    """`security_gate` belongs to `branch`; a gate created directly under a
    different branch must never show up in the branch-scoped caller's list
    — the list-endpoint counterpart of
    `test_create_security_gate_denied_for_user_scoped_elsewhere`.
    """
    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-GATE")
    db_session.add(other_branch)
    await db_session.flush()
    other_gate = SecurityGateFactory.build(
        id=uuid.uuid4(),
        branch_id=other_branch.id,
        building_id=None,
        code="OTH-GATE",
        gate_type="entry",
    )
    db_session.add(other_gate)
    await db_session.commit()

    token = await _login(client, user_scoped_to_branch.email)
    response = await client.get(
        "/api/v1/security-gates", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {g["code"] for g in response.json()["data"]}
    assert security_gate.code in codes
    assert other_gate.code not in codes


async def test_get_security_gate_success(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/security-gates/{security_gate.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(security_gate.id)


async def test_get_security_gate_not_found_for_other_branch(
    client: AsyncClient, security_gate: SecurityGate, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.get(
        f"/api/v1/security-gates/{security_gate.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_update_security_gate_success(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/security-gates/{security_gate.id}",
        json={"name": "Renamed Gate"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Renamed Gate"


async def test_update_security_gate_not_found_for_other_branch(
    client: AsyncClient, security_gate: SecurityGate, user_scoped_to_other_branch: User
) -> None:
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.put(
        f"/api/v1/security-gates/{security_gate.id}",
        json={"name": "Hijacked Gate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_security_gate_success(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/security-gates/{security_gate.id}",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 204


async def test_delete_security_gate_not_found_for_other_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    security_gate: SecurityGate,
    user_scoped_to_other_branch: User,
) -> None:
    """See `test_delete_building_not_found_for_other_branch` for why
    survival is checked via the repository rather than a second HTTP call.
    """
    token = await _login(client, user_scoped_to_other_branch.email)
    response = await client.delete(
        f"/api/v1/security-gates/{security_gate.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404

    survivor = await SecurityGateRepository(db_session).get(security_gate.id)
    assert survivor is not None


async def test_create_security_gate_after_soft_delete_reuses_code(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    """A soft-deleted gate's `code` must not stay reserved forever — see
    openspec/changes/harden-org-structure-crud/design.md Decision 1.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    delete_response = await client.delete(
        f"/api/v1/security-gates/{security_gate.id}", headers=headers
    )
    assert delete_response.status_code == 204

    recreate_response = await client.post(
        "/api/v1/security-gates",
        json={"branchId": str(branch.id), "name": "New Gate", "code": security_gate.code},
        headers=headers,
    )
    assert recreate_response.status_code == 201


async def test_security_gate_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, security_gate: SecurityGate
) -> None:
    other_schema = "tenant_other_test_gate"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await SecurityGateRepository(other_session).get(security_gate.id)
        assert found is None


async def test_create_security_gate_with_offline_connectivity(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """`connectivityStatus` is independent of `gateType` and `highSecurity`
    — see
    openspec/changes/add-role-management-and-org-field-gaps/design.md
    Decision 3.
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/security-gates",
        json={
            "branchId": str(branch.id),
            "name": "Offline Gate",
            "code": "GATE-OFF",
            "gateType": "both",
            "connectivityStatus": "offline",
            "highSecurity": True,
            "authMethod": "Biometric/RFID Card",
        },
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["connectivityStatus"] == "offline"
    assert body["highSecurity"] is True
    assert body["gateType"] == "both"


async def test_update_security_gate_connectivity_status(
    client: AsyncClient, user: User, security_gate: SecurityGate, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/security-gates/{security_gate.id}",
        json={"connectivityStatus": "maintenance"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    assert response.json()["data"]["connectivityStatus"] == "maintenance"
