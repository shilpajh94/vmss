"""End-to-end staff/admin workflow chain (openspec `add-end-to-end-workflow-tests`,
tasks 1.1-5.3).

Unlike every other test in this repo, this one does not use the shared
`client` fixture (`conftest.py`): that fixture hardcodes `get_tenant_db` to
always yield the same `db_session`, bound to the one default test schema
(`tenant_acme_test`) — it never exercises the real per-request dynamic
schema resolution `core/tenancy.py::get_tenant_db` performs in production.
This test builds its own `AsyncClient` so it can provision a genuinely new
tenant schema via `POST /platform/tenants` and then rebind `get_tenant_db`
to that real schema for everything after — see design.md's "Staff/admin
chain: a bespoke `get_tenant_db` override" decision.

The chain, each step feeding the next step's real response forward (never a
hardcoded id/token):
platform login -> tenant provisioning -> one documented non-API seed step
(see `_seed_first_admin` below) -> tenant-admin login -> org structure
(company -> branch -> building -> floor -> department -> reception desk ->
security gate) -> a second staff user + branch-role grant -> visitor
category + approval workflow rule -> listings reflecting everything created
-> a PUT/DELETE close-out with follow-up GETs -> the cross-branch reports
rollup reflecting the final state.

Deviation from design.md: design.md's "Slug uniqueness and schema cleanup"
section says this test should *not* drop the schema it provisions
afterward, reasoning by analogy to `make_tenant_schema` (used by every
tenant-isolation test), which also never drops what it creates. That
analogy doesn't hold here: `make_tenant_schema` only creates empty tables,
while this test provisions through the real `POST /platform/tenants` path,
which runs `auth/rbac_catalog.py::seed_default_roles` and so leaves
`role_permissions` rows in the new schema that FK-reference the *shared*
`global.permissions` table. Left behind, those rows make every later
test's `db_session` fixture teardown (`conftest.py`) fail with a foreign
key violation trying to clear that same global table — confirmed by
running this test and observing the very next test's `db_session` teardown
break. This is exactly the failure mode `platform/tests.py`'s own
`test_create_tenant_provisions_real_schema` and
`test_create_tenant_success_via_endpoint` already guard against by
dropping their provisioned schema in a `finally` block, so this test
follows that established precedent instead.
"""

import uuid
from collections.abc import AsyncGenerator, Callable

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from factories import UserFactory
from vmss_api.auth.models import Role, UserBranchRole
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.security import hash_password
from vmss_api.core.tenancy import get_tenant_db
from vmss_api.main import app
from vmss_api.platform.models import SuperAdmin, TenantUserIndex


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _tenant_db_not_yet_provisioned() -> AsyncSession:
    """Placeholder `get_tenant_db` override installed before task 1.3
    provisions a real tenant and rebinds this override to it (see
    `_bind_tenant_db_override` below). Raises clearly rather than silently
    resolving against no schema (or the wrong one) if anything in this test
    reaches a tenant-scoped endpoint too early.
    """
    raise AssertionError(
        "get_tenant_db was called before the staff/admin workflow test provisioned its "
        "tenant and rebound this override (task 1.3) — every tenant-scoped call in this "
        "chain must happen after that point."
    )


def _bind_tenant_db_override(schema_name: str) -> Callable[[], AsyncGenerator[AsyncSession]]:
    """Builds the real `get_tenant_db` override for one already-provisioned
    tenant schema, wrapping `core.database.tenant_session_scope` the same
    way the real dependency does (`core/tenancy.py::get_tenant_db`) — the
    only difference is the schema name comes from this test's own
    `POST /platform/tenants` call instead of a JWT claim.
    """

    async def _override() -> AsyncGenerator[AsyncSession]:
        async with tenant_session_scope(schema_name) as session:
            yield session

    return _override


async def _seed_first_admin(
    schema_name: str, *, tenant_id: uuid.UUID, email: str, password: str
) -> None:
    """The one non-API step in this chain (design.md Context point 2):
    `platform/service.py::create_tenant` provisions a tenant's schema and
    seeds its RBAC catalog (`auth/rbac_catalog.py::seed_default_roles`), but
    creates no `User` row — there is no self-registration or
    first-admin-bootstrap endpoint anywhere in this API today. Every
    `POST /auth/users` call requires `users:manage`, which requires already
    being authenticated as someone in that tenant, so a brand-new tenant's
    very first user cannot come from this API. This mirrors what a real
    onboarding runbook or seed script does in production, and looks up the
    already-seeded `"admin"` role by name rather than re-creating it, to
    prove `seed_default_roles`' output is actually usable.
    """
    async with tenant_session_scope(schema_name) as tenant_db:
        admin_role = (
            await tenant_db.execute(select(Role).where(Role.name == "admin"))
        ).scalar_one()

        branch_role = UserBranchRole(id=uuid.uuid4(), role=admin_role, branch_id=None)
        first_admin = UserFactory.build(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            full_name="Seed Admin",
            branch_roles=[branch_role],
        )
        tenant_db.add(first_admin)
        await tenant_db.flush()
        tenant_db.add(TenantUserIndex(email=email, tenant_id=tenant_id, user_id=first_admin.id))
        await tenant_db.commit()


async def _run_workflow_after_provisioning(
    client: AsyncClient, *, suffix: str, tenant_id: uuid.UUID, schema_name: str
) -> None:
    # --- 2. The one non-API seed step -----------------------------------
    admin_email = f"seed-admin-{suffix}@e2e-staff.example"
    admin_password = "correct-password"
    await _seed_first_admin(
        schema_name, tenant_id=tenant_id, email=admin_email, password=admin_password
    )

    # --- 3. Tenant-admin login ------------------------------------------
    admin_login = await client.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": admin_password}
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["data"]["accessToken"]
    assert admin_token
    admin_headers = _bearer(admin_token)

    # --- 4. Org structure chain -----------------------------------------
    company_response = await client.post(
        "/api/v1/company",
        json={"legalName": "E2E Staff Admin Co Pvt Ltd"},
        headers=admin_headers,
    )
    assert company_response.status_code == 201

    branch_response = await client.post(
        "/api/v1/branches",
        json={"name": "HQ Branch", "code": f"HQ-{suffix}"},
        headers=admin_headers,
    )
    assert branch_response.status_code == 201
    branch_id = branch_response.json()["data"]["id"]

    building_response = await client.post(
        "/api/v1/buildings",
        json={"branchId": branch_id, "name": "Tower A", "code": f"TWR-{suffix}"},
        headers=admin_headers,
    )
    assert building_response.status_code == 201
    building_id = building_response.json()["data"]["id"]

    floor_response = await client.post(
        "/api/v1/floors",
        json={"buildingId": building_id, "name": "Ground Floor", "floorNumber": 0},
        headers=admin_headers,
    )
    assert floor_response.status_code == 201
    floor_id = floor_response.json()["data"]["id"]

    department_response = await client.post(
        "/api/v1/departments",
        json={
            "branchId": branch_id,
            "floorId": floor_id,
            "name": "Human Resources",
            "code": f"HR-{suffix}",
        },
        headers=admin_headers,
    )
    assert department_response.status_code == 201
    department_id = department_response.json()["data"]["id"]

    desk_response = await client.post(
        "/api/v1/reception-desks",
        json={"floorId": floor_id, "name": "Main Desk", "code": f"DESK-{suffix}"},
        headers=admin_headers,
    )
    assert desk_response.status_code == 201

    gate_response = await client.post(
        "/api/v1/security-gates",
        json={
            "branchId": branch_id,
            "buildingId": building_id,
            "name": "Main Gate",
            "code": f"GATE-{suffix}",
            "gateType": "entry",
        },
        headers=admin_headers,
    )
    assert gate_response.status_code == 201
    gate_id = gate_response.json()["data"]["id"]

    # --- Second staff user + branch-role grant, using the real branch id
    # from above (design.md's reordering note: this can't happen until a
    # real branch exists).
    staff_email = f"staff-{suffix}@e2e-staff.example"
    create_user_response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": staff_email,
            "password": "correct-password",
            "fullName": "Second Staff Member",
        },
        headers=admin_headers,
    )
    assert create_user_response.status_code == 201
    staff_user_id = create_user_response.json()["data"]["id"]

    roles_response = await client.get("/api/v1/auth/roles", headers=admin_headers)
    assert roles_response.status_code == 200
    roles_by_name = {r["name"]: r["id"] for r in roles_response.json()["data"]}
    admin_role_id = roles_by_name["admin"]
    reception_role_id = roles_by_name["reception"]

    assign_role_response = await client.post(
        f"/api/v1/auth/users/{staff_user_id}/branch-roles",
        json={"roleId": reception_role_id, "branchId": branch_id},
        headers=admin_headers,
    )
    assert assign_role_response.status_code == 201

    # `GET /auth/employees` only ever returns rows that join
    # `User -> Department -> Floor -> Building` (see
    # `auth/repository.py::UserRepository.list_employees_page`) — a plain
    # staff account created via `POST /auth/users` has no
    # `departmentId`/`employeeCode` and so never appears there, regardless
    # of any branch-role grant. Reconciling the same email through the
    # employee-directory sync endpoint (using the real department id from
    # above) is what actually makes this person show up as an "employee" —
    # necessary for section 5.1's listing assertion to be meaningful rather
    # than vacuous.
    sync_response = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": staff_email,
                    "fullName": "Second Staff Member",
                    "employeeCode": f"EMP-{suffix}",
                    "departmentId": department_id,
                }
            ]
        },
        headers=admin_headers,
    )
    assert sync_response.status_code == 200
    assert staff_email in sync_response.json()["data"]["updated"]

    category_response = await client.post(
        "/api/v1/visitor-categories",
        json={"name": "General Visitor", "code": f"GEN-{suffix}"},
        headers=admin_headers,
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["data"]["id"]

    rule_response = await client.post(
        "/api/v1/approval-workflow-rules",
        json={
            "visitorCategoryId": category_id,
            "stepOrder": 1,
            "approverRoleId": admin_role_id,
        },
        headers=admin_headers,
    )
    assert rule_response.status_code == 201

    # --- 5. Listing, CRUD close-out, dashboard rollup --------------------
    employees_response = await client.get("/api/v1/auth/employees", headers=admin_headers)
    assert employees_response.status_code == 200
    assert staff_user_id in {e["id"] for e in employees_response.json()["data"]}

    branches_list_response = await client.get("/api/v1/branches", headers=admin_headers)
    assert branches_list_response.status_code == 200
    assert branch_id in {b["id"] for b in branches_list_response.json()["data"]}

    categories_list_response = await client.get("/api/v1/visitor-categories", headers=admin_headers)
    assert categories_list_response.status_code == 200
    assert category_id in {c["id"] for c in categories_list_response.json()["data"]}

    update_department_response = await client.put(
        f"/api/v1/departments/{department_id}",
        json={"name": "Human Resources (Renamed)"},
        headers=admin_headers,
    )
    assert update_department_response.status_code == 200
    assert update_department_response.json()["data"]["name"] == "Human Resources (Renamed)"

    get_department_response = await client.get(
        f"/api/v1/departments/{department_id}", headers=admin_headers
    )
    assert get_department_response.status_code == 200
    assert get_department_response.json()["data"]["name"] == "Human Resources (Renamed)"

    delete_gate_response = await client.delete(
        f"/api/v1/security-gates/{gate_id}", headers=admin_headers
    )
    assert delete_gate_response.status_code == 204

    get_gate_response = await client.get(f"/api/v1/security-gates/{gate_id}", headers=admin_headers)
    assert get_gate_response.status_code == 404

    rollup_response = await client.get("/api/v1/reports/branches/rollup", headers=admin_headers)
    assert rollup_response.status_code == 200
    rollup = rollup_response.json()["data"]
    assert rollup["totalBranches"] == 1
    assert rollup["totalSecurityGates"] == 0
    assert rollup["totalActiveEmployees"] == 1

    branch_rollup = next(b for b in rollup["branches"] if b["branchId"] == branch_id)
    assert branch_rollup["buildingCount"] == 1
    assert branch_rollup["floorCount"] == 1
    assert branch_rollup["departmentCount"] == 1
    assert branch_rollup["receptionDeskCount"] == 1
    assert branch_rollup["securityGateCount"] == 0
    assert branch_rollup["activeEmployeeCount"] == 1


async def test_staff_admin_full_workflow(superadmin: SuperAdmin, db_session: AsyncSession) -> None:
    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_tenant_db] = _tenant_db_not_yet_provisioned
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # --- 1. Platform login + tenant provisioning --------------------
            platform_login = await client.post(
                "/api/v1/platform/auth/login",
                json={"email": superadmin.email, "password": "correct-password"},
            )
            assert platform_login.status_code == 200
            platform_token = platform_login.json()["data"]["accessToken"]
            assert platform_token

            suffix = uuid.uuid4().hex[:8]
            slug = f"e2e-staff-{suffix}"
            create_tenant_response = await client.post(
                "/api/v1/platform/tenants",
                json={"name": "E2E Staff Admin Co", "slug": slug},
                headers=_bearer(platform_token),
            )
            assert create_tenant_response.status_code == 201
            tenant_data = create_tenant_response.json()["data"]
            tenant_id = uuid.UUID(tenant_data["id"])
            schema_name = f"{settings.tenant_schema_prefix}{slug}"

            app.dependency_overrides[get_tenant_db] = _bind_tenant_db_override(schema_name)

            try:
                await _run_workflow_after_provisioning(
                    client, suffix=suffix, tenant_id=tenant_id, schema_name=schema_name
                )
            finally:
                # See the module docstring's "Deviation from design.md" note:
                # this schema was seeded with `role_permissions` rows that FK
                # into the shared `global.permissions` table, so leaving it
                # behind (as design.md originally called for) breaks every
                # later test's `db_session` teardown, not just this one.
                await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                await db_session.commit()
    finally:
        app.dependency_overrides.clear()
