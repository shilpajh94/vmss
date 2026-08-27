import uuid
from collections.abc import Callable

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BuildingFactory, DepartmentFactory, FloorFactory, RoleFactory, UserFactory
from vmss_api.auth.models import AuditLog, Permission, Role, User, UserBranchRole
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Department
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant


@pytest_asyncio.fixture(autouse=True)
def _default_tenant_slug_matches_test_tenant(monkeypatch):
    """`GET /auth/employees` and `GET /auth/employees/directory` are both
    public listing endpoints and fall back to `settings.default_tenant_slug`
    when no token resolves a tenant — mirrors `org_structure/tests.py`'s
    fixture of the same name.
    """
    monkeypatch.setattr(settings, "default_tenant_slug", "acme-test")


async def _login(client: AsyncClient, email: str, password: str = "correct-password") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["accessToken"]


async def test_login_success(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "correct-password"}
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["tokenType"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401


async def test_login_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_login_rate_limit_trips(client: AsyncClient, user: User, monkeypatch) -> None:
    """`slowapi`'s `Limiter` is disabled outright in the test environment
    (`core/rate_limit.py`: `enabled=settings.environment != "test"`) —
    flipped on here for just this one test to exercise the 429 path
    (security-architecture.md §2), mirroring
    `invitations/tests.py::test_track_rate_limit_trips`.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [
        await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
        )
        for _ in range(10)
    ]
    assert any(r.status_code == 429 for r in responses)


async def test_login_rejects_non_admin_account(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    """Reception/Security/Host (and any custom non-Admin role) must sign in
    via SSO, not password login — `test_login_success` above already
    covers the Admin happy path via the `user` fixture (a company-wide
    Admin). See `openspec/changes/separate-admin-staff-login`.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email="reception-login-test@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Reception User",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-password"},
    )
    assert response.status_code == 403


async def test_tenant_schema_isolation(make_tenant_schema, open_tenant_session, user: User) -> None:
    """A session bound to a *different* tenant's schema must not see this
    tenant's `users` row — under schema-per-tenant, isolation is which
    physical Postgres schema a connection is pointed at, not a WHERE clause
    on a shared table. See database-architecture.md §3 and
    testing-standards.md §2 (the tenant-isolation case every feature's
    tests must cover).
    """
    other_schema = "tenant_other_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await UserRepository(other_session).get_by_id(user.id)
        assert found is None


async def test_get_my_profile(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["email"] == user.email
    assert any(r["roleName"] == "admin" and r["branchId"] is None for r in body["branchRoles"])


async def test_get_my_profile_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_create_user_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "new-hire@acme-test.example",
            "password": "correct-password",
            "fullName": "New Hire",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["branchRoles"] == []


async def test_create_user_duplicate_email_conflict(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/users",
        json={"email": user.email, "password": "correct-password", "fullName": "Duplicate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_create_user_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    """Also asserts the response body shape: `HTTPException`s raised across
    the app (401/403/404/409/...) go through `core/middleware.py`'s
    `http_exception_handler`, so a 403 here is the same
    `{success, message, errors}` envelope every other response uses — not
    FastAPI's default `{"detail": ...}` body. See security-architecture.md §1.
    """
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "nobody@acme-test.example",
            "password": "correct-password",
            "fullName": "Nobody",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "detail" not in body
    assert body["message"]


async def test_assign_branch_role_scopes_access_to_that_branch(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    user_without_permissions: User,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """Exercises the full grant flow end to end: an Admin assigns a role to
    another user scoped to one branch, and that user then gains access to
    exactly that branch (via `GET /branches/current`) — not company-wide.
    """
    # `Permission` is global-schema and its `code` is unique — the `user`
    # fixture already seeded "branches:view", so reuse it instead of
    # inserting a duplicate.
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[existing])
    db_session.add(role)
    await db_session.commit()

    admin_token = await _login(client, user.email)
    assign_response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert assign_response.status_code == 201
    assert assign_response.json()["data"]["roleName"] == "reception"

    # The test `client` fixture routes every request's tenant-bound session
    # to this same `db_session`, so `user_without_permissions.branch_roles`
    # (already loaded as empty when its fixture ran) sits in the identity
    # map and won't pick up the grant just inserted above by itself — unlike
    # a real request, which always opens a fresh, unexpired session. Expire
    # just that relationship (not the whole object — `.email` below is read
    # as a plain in-memory attribute, and expiring it too would force an
    # implicit reload outside any active session IO context).
    db_session.expire(user_without_permissions, ["branch_roles"])

    granted_token = issue_token(user_without_permissions)
    current = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {granted_token}", "X-Branch-ID": str(branch.id)},
    )
    assert current.status_code == 200


async def test_assign_branch_role_requires_permission(
    client: AsyncClient,
    user_without_permissions: User,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(user_without_permissions.id), "branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_assign_branch_role_unknown_role_not_found(
    client: AsyncClient, user: User, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(uuid.uuid4()), "branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_assign_branch_role_unknown_branch_not_found(
    client: AsyncClient, db_session: AsyncSession, user: User, user_without_permissions: User
) -> None:
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(
        id=uuid.uuid4(), name="reception-unknown-branch", permissions=[existing]
    )
    db_session.add(role)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_assign_visitor_role_to_user_rejected(
    client: AsyncClient, db_session: AsyncSession, user: User, user_without_permissions: User
) -> None:
    """Visitors never authenticate through this JWT/RBAC system
    (security-architecture.md §2), so the seeded "visitor" role must never
    be grantable to a `User` — see auth/service.py::assign_branch_role.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="visitor", permissions=[])
    db_session.add(role)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

    grants = (
        (
            await db_session.execute(
                select(UserBranchRole).where(UserBranchRole.user_id == user_without_permissions.id)
            )
        )
        .scalars()
        .all()
    )
    assert grants == []


async def _make_department(db_session: AsyncSession, branch: Branch) -> Department:
    building = BuildingFactory.build(id=uuid.uuid4(), branch_id=branch.id, code="TWR-A")
    db_session.add(building)
    await db_session.flush()
    floor = FloorFactory.build(id=uuid.uuid4(), building_id=building.id, floor_number=0)
    db_session.add(floor)
    await db_session.flush()
    department = DepartmentFactory.build(
        id=uuid.uuid4(), branch_id=branch.id, floor_id=floor.id, code="ENG"
    )
    db_session.add(department)
    await db_session.commit()
    return department


async def test_sync_employee_directory_creates_and_deactivates(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    """First sync creates two employees; a second sync that only re-sends
    one of them deactivates the other — the "full authoritative batch"
    reconciliation semantics decided for this feature (project-rules.md's
    "manual bulk sync" scope).
    """
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    first_sync = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "alice@acme-test.example",
                    "fullName": "Alice Employee",
                    "employeeCode": "EMP-001",
                    "departmentId": str(department.id),
                },
                {
                    "email": "bob@acme-test.example",
                    "fullName": "Bob Employee",
                    "employeeCode": "EMP-002",
                },
            ]
        },
        headers=headers,
    )
    assert first_sync.status_code == 200
    first_body = first_sync.json()["data"]
    assert set(first_body["created"]) == {"alice@acme-test.example", "bob@acme-test.example"}
    assert first_body["deactivated"] == []

    second_sync = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "alice@acme-test.example",
                    "fullName": "Alice Employee",
                    "employeeCode": "EMP-001",
                    "departmentId": str(department.id),
                }
            ]
        },
        headers=headers,
    )
    assert second_sync.status_code == 200
    second_body = second_sync.json()["data"]
    assert second_body["updated"] == ["alice@acme-test.example"]
    assert second_body["deactivated"] == ["bob@acme-test.example"]

    bob = await UserRepository(db_session).get_by_email("bob@acme-test.example")
    assert bob is not None
    assert bob.is_active is False


async def test_sync_employee_directory_unknown_department_not_found(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "carol@acme-test.example",
                    "fullName": "Carol Employee",
                    "employeeCode": "EMP-003",
                    "departmentId": str(uuid.uuid4()),
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_sync_employee_directory_duplicate_employee_code_in_batch_conflict(
    client: AsyncClient, user: User
) -> None:
    """Two new employees in the same batch sharing an `employeeCode` violate
    the column's unique constraint on commit — `auth/service.py`'s
    `IntegrityError` handling must translate that into a 409, not a raw
    500 (`auth/service.py:376-380`).
    """
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {"email": "erin@acme-test.example", "fullName": "Erin", "employeeCode": "EMP-DUP"},
                {
                    "email": "frank@acme-test.example",
                    "fullName": "Frank",
                    "employeeCode": "EMP-DUP",
                },
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


async def test_sync_employee_directory_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {"email": "dave@acme-test.example", "fullName": "Dave", "employeeCode": "EMP-004"}
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_create_employee_success(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "grace@acme-test.example",
            "fullName": "Grace Employee",
            "employeeCode": "EMP-010",
            "departmentId": str(department.id),
            "phoneNumber": "+1-555-0100",
            "designation": "Engineer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["email"] == "grace@acme-test.example"
    assert body["employeeCode"] == "EMP-010"
    assert body["departmentId"] == str(department.id)
    assert body["phoneNumber"] == "+1-555-0100"
    assert body["designation"] == "Engineer"
    assert body["isActive"] is True


async def test_create_employee_visible_in_listing_without_sync(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    """Regression test: creating an employee via `POST /auth/employees` must
    make it show up in `GET /auth/employees` right away, with no
    `/auth/employees/sync` call in between — this is the bug the frontend
    team reported.
    """
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "henry@acme-test.example",
            "fullName": "Henry Employee",
            "employeeCode": "EMP-011",
            "departmentId": str(department.id),
        },
        headers=headers,
    )
    assert create_response.status_code == 201

    list_response = await client.get(
        f"/api/v1/auth/employees?departmentId={department.id}",
        headers={**headers, "X-Branch-ID": str(branch.id)},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["email"] == "henry@acme-test.example"


async def test_create_employee_does_not_deactivate_others(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "ida@acme-test.example",
                    "fullName": "Ida Employee",
                    "employeeCode": "EMP-012",
                    "departmentId": str(department.id),
                }
            ]
        },
        headers=headers,
    )

    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "jack@acme-test.example",
            "fullName": "Jack Employee",
            "employeeCode": "EMP-013",
            "departmentId": str(department.id),
        },
        headers=headers,
    )
    assert response.status_code == 201

    ida = await UserRepository(db_session).get_by_email("ida@acme-test.example")
    assert ida is not None
    assert ida.is_active is True


async def test_create_employee_duplicate_email_conflict(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": user.email,
            "fullName": "Duplicate",
            "employeeCode": "EMP-014",
            "departmentId": str(department.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert await UserRepository(db_session).get_by_employee_code("EMP-014") is None


async def test_create_employee_unknown_department_not_found(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "kelly@acme-test.example",
            "fullName": "Kelly Employee",
            "employeeCode": "EMP-015",
            "departmentId": str(uuid.uuid4()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert await UserRepository(db_session).get_by_email("kelly@acme-test.example") is None


async def test_create_employee_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch, db_session: AsyncSession
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "liam@acme-test.example",
            "fullName": "Liam Employee",
            "employeeCode": "EMP-016",
            "departmentId": str(department.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert await UserRepository(db_session).get_by_email("liam@acme-test.example") is None


async def test_create_employee_tenant_schema_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    branch: Branch,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """Same tenant-isolation case as `test_tenant_schema_isolation` above,
    applied to the new endpoint — see testing-standards.md §2.
    """
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "mia@acme-test.example",
            "fullName": "Mia Employee",
            "employeeCode": "EMP-017",
            "departmentId": str(department.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    other_schema = "tenant_other_employee_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        found = await UserRepository(other_session).get_by_email("mia@acme-test.example")
        assert found is None


async def test_list_employees_success(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "erin@acme-test.example",
                    "fullName": "Erin Employee",
                    "employeeCode": "EMP-005",
                    "departmentId": str(department.id),
                }
            ]
        },
        headers=headers,
    )

    response = await client.get(
        f"/api/v1/auth/employees?departmentId={department.id}",
        headers={**headers, "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["email"] == "erin@acme-test.example"


async def test_list_employees_includes_users_with_no_employee_code(
    client: AsyncClient, user: User
) -> None:
    """`user` (a company-wide Admin) was created directly, not through
    `sync_employee_directory`/`create_employee`, so it has no
    `employeeCode` — it still belongs in this directory
    (`UserRepository.list_employees_page` no longer requires one).
    """
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()["data"]}
    assert user.email in emails


async def test_list_employees_without_branch_header_includes_employee_with_no_department(
    client: AsyncClient, user: User
) -> None:
    """A departmentless employee still appears in an unscoped ("all
    branches") listing — `UserRepository.list_employees_page`'s outer join
    against Department/Floor/Building, not an inner one. They only drop
    out of a branch-scoped view, since there's no chain to resolve them to
    a specific branch — see the test right below.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "dana@acme-test.example",
                    "fullName": "Dana Employee",
                    "employeeCode": "EMP-006",
                }
            ]
        },
        headers=headers,
    )

    response = await client.get("/api/v1/auth/employees", headers=headers)
    assert response.status_code == 200
    names = {e["fullName"] for e in response.json()["data"]}
    assert "Dana Employee" in names


async def test_list_employees_with_branch_header_excludes_employee_with_no_department(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "dana@acme-test.example",
                    "fullName": "Dana Employee",
                    "employeeCode": "EMP-006",
                }
            ]
        },
        headers=headers,
    )

    response = await client.get(
        "/api/v1/auth/employees", headers={**headers, "X-Branch-ID": str(branch.id)}
    )
    assert response.status_code == 200
    names = {e["fullName"] for e in response.json()["data"]}
    assert "Dana Employee" not in names


async def _branch_scoped_employee_viewer(
    db_session: AsyncSession, tenant: Tenant, branch_id: uuid.UUID
) -> User:
    # `Permission.code` is global-schema and unique — the `user` fixture
    # (a session-scoped company-wide Admin) already seeded "employees:view",
    # so reuse it instead of inserting a duplicate.
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "employees:view"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="employee-viewer", permissions=[existing])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Employee Viewer",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def test_list_employees_without_branch_header_scopes_to_every_authorized_branch(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    """Omitting `X-Branch-ID` on a list request returns every branch in the
    resolved tenant — there is no longer a notion of a caller's authorized
    branches, since the endpoint requires no caller.
    """
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "erin@acme-test.example",
                    "fullName": "Erin Employee",
                    "employeeCode": "EMP-005",
                    "departmentId": str(department.id),
                }
            ]
        },
        headers=headers,
    )

    response = await client.get("/api/v1/auth/employees", headers=headers)
    assert response.status_code == 200
    body = response.json()
    emails = {row["email"] for row in body["data"]}
    assert "erin@acme-test.example" in emails


async def test_list_employees_not_scoped_by_caller_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    tenant: Tenant,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    """Listing no longer requires `employees:view`, so a caller scoped to
    only one branch (or no caller at all) no longer narrows the result —
    every branch's employees are in scope regardless of the token
    presented, superseding the pre-public-listing behavior this test used
    to assert. No `X-Branch-ID` is sent, so this is also an unscoped
    listing: `user` (admin) and `viewer` — both department-less — appear
    alongside the two synced employees, per
    `UserRepository.list_employees_page`'s outer join
    (`test_list_employees_without_branch_header_includes_employee_with_no_department`
    covers that case in isolation).
    """
    department = await _make_department(db_session, branch)
    admin_token = await _login(client, user.email)
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "own-branch@acme-test.example",
                    "fullName": "Own Branch Employee",
                    "employeeCode": "EMP-006",
                    "departmentId": str(department.id),
                }
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    other_branch = Branch(id=uuid.uuid4(), name="Other Branch", code="OTHER-EMP")
    db_session.add(other_branch)
    await db_session.flush()
    await db_session.commit()
    other_department = await _make_department(db_session, other_branch)
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "other-branch@acme-test.example",
                    "fullName": "Other Branch Employee",
                    "employeeCode": "EMP-007",
                    "departmentId": str(other_department.id),
                }
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    viewer = await _branch_scoped_employee_viewer(db_session, tenant, branch.id)
    viewer_token = issue_token(viewer)
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()["data"]}
    assert emails == {
        "own-branch@acme-test.example",
        "other-branch@acme-test.example",
        user.email,
        viewer.email,
    }


async def test_list_employees_no_auth_header_succeeds(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    """Listing is public — no bearer token required."""
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "no-token@acme-test.example",
            "fullName": "No Token Employee",
            "employeeCode": "EMP-020",
            "departmentId": str(department.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get("/api/v1/auth/employees")
    assert response.status_code == 200
    assert "no-token@acme-test.example" in {e["email"] for e in response.json()["data"]}


async def test_list_employees_invalid_token_still_succeeds(
    client: AsyncClient, tenant: Tenant
) -> None:
    """An expired/malformed token is simply not inspected for this endpoint."""
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 200


async def test_list_employees_rate_limit_trips(
    client: AsyncClient, tenant: Tenant, monkeypatch
) -> None:
    """Now that this endpoint is public, it must be rate-limited by client
    IP like every other unauthenticated endpoint — see
    `security-architecture.md` §2 and
    `org_structure/tests.py`'s equivalent test for the public listing
    endpoints there. `slowapi`'s `Limiter` is disabled in the test
    environment by default, flipped on here for just this one test.
    """
    monkeypatch.setattr(limiter, "enabled", True)
    responses = [await client.get("/api/v1/auth/employees") for _ in range(70)]
    assert any(r.status_code == 429 for r in responses)


async def test_list_employees_tenant_isolation(
    client: AsyncClient,
    make_tenant_schema,
    open_tenant_session,
    tenant: Tenant,
) -> None:
    """The tenant-isolation case testing-standards.md §2 requires for this
    change — an employee that only exists in a different tenant's schema
    must never surface in the public listing, which always resolves to
    `settings.default_tenant_slug`'s schema when no token is presented.
    """
    other_schema = "tenant_other_test_employee_isolation"
    suffix = uuid.uuid4().hex[:8]
    other_email = f"other-tenant-{suffix}@example.com"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_session.add(
            UserFactory.build(
                id=uuid.uuid4(),
                email=other_email,
                hashed_password=hash_password("correct-password"),
                full_name="Other Tenant Employee",
                employee_code=f"OTHER-EMP-{suffix}",
            )
        )
        await other_session.commit()

    response = await client.get("/api/v1/auth/employees")
    assert response.status_code == 200
    assert other_email not in {e["email"] for e in response.json()["data"]}


async def test_list_employees_filter_by_email_exact_match(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "jane@acme-test.example",
                    "fullName": "Jane Employee",
                    "employeeCode": "EMP-010",
                    "departmentId": str(department.id),
                },
                {
                    "email": "john@acme-test.example",
                    "fullName": "John Employee",
                    "employeeCode": "EMP-011",
                    "departmentId": str(department.id),
                },
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get("/api/v1/auth/employees?email=jane@acme-test.example")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["email"] == "jane@acme-test.example"


async def test_list_employees_filter_by_role(
    client: AsyncClient, db_session: AsyncSession, user: User, tenant: Tenant, branch: Branch
) -> None:
    """A role held at any branch qualifies, and an employee holding that
    role at more than one branch is not duplicated in the result.
    """
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "receptionist@acme-test.example",
                    "fullName": "Receptionist Employee",
                    "employeeCode": "EMP-012",
                    "departmentId": str(department.id),
                },
                {
                    "email": "plain@acme-test.example",
                    "fullName": "Plain Employee",
                    "employeeCode": "EMP-013",
                    "departmentId": str(department.id),
                },
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    receptionist = await UserRepository(db_session).get_by_email("receptionist@acme-test.example")
    assert receptionist is not None
    receptionist_role = RoleFactory.build(id=uuid.uuid4(), name="Receptionist")
    other_branch = Branch(id=uuid.uuid4(), name="Second Branch", code="SECOND-EMP")
    db_session.add_all([receptionist_role, other_branch])
    await db_session.flush()
    db_session.add_all(
        [
            UserBranchRole(
                id=uuid.uuid4(),
                user_id=receptionist.id,
                role=receptionist_role,
                branch_id=branch.id,
            ),
            UserBranchRole(
                id=uuid.uuid4(),
                user_id=receptionist.id,
                role=receptionist_role,
                branch_id=other_branch.id,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/auth/employees?role=Receptionist")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["email"] == "receptionist@acme-test.example"


async def _make_role_user(
    db_session: AsyncSession,
    tenant: Tenant,
    role: Role,
    *,
    email: str,
    full_name: str,
    is_active: bool = True,
) -> User:
    """A user granted `role` company-wide, deliberately with no
    `employee_code`/`department_id` — a `host` account isn't necessarily
    reconciled through `sync_employee_directory`, so the directory listing
    must not require either.
    """
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    new_user = UserFactory.build(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("correct-password"),
        full_name=full_name,
        is_active=is_active,
        branch_roles=[branch_role],
    )
    db_session.add(new_user)
    await db_session.flush()
    db_session.add(TenantUserIndex(email=email, tenant_id=tenant.id, user_id=new_user.id))
    await db_session.commit()
    return new_user


async def test_list_employee_directory_no_auth_header_succeeds(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    """Public — no bearer token, same rationale as
    `org_structure/router.py::list_branches`: a pre-registration form needs
    a "who are you visiting" picker before a visitor authenticates. Only
    the reduced, non-PII field set is exposed — see `EmployeeDirectoryOut`.
    No department assigned, and it still shows up (`UserRepository.list_hosts_page`
    isn't branch/department scoped).
    """
    host_role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(host_role)
    await db_session.commit()
    await _make_role_user(
        db_session, tenant, host_role, email="erin@acme-test.example", full_name="Erin Host"
    )

    response = await client.get("/api/v1/auth/employees/directory")
    assert response.status_code == 200
    body = response.json()
    names = {e["fullName"] for e in body["data"]}
    assert "Erin Host" in names
    for entry in body["data"]:
        assert "email" not in entry
        assert "phoneNumber" not in entry
        assert "employeeCode" not in entry


async def test_list_employee_directory_excludes_inactive_and_non_host_roles(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    host_role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    reception_role = RoleFactory.build(id=uuid.uuid4(), name="reception", permissions=[])
    db_session.add_all([host_role, reception_role])
    await db_session.commit()

    await _make_role_user(
        db_session, tenant, host_role, email="alice@acme-test.example", full_name="Alice Host"
    )
    await _make_role_user(
        db_session,
        tenant,
        host_role,
        email="bob@acme-test.example",
        full_name="Bob Host",
        is_active=False,
    )
    await _make_role_user(
        db_session,
        tenant,
        reception_role,
        email="carol@acme-test.example",
        full_name="Carol Reception",
    )

    response = await client.get("/api/v1/auth/employees/directory")
    assert response.status_code == 200
    names = {e["fullName"] for e in response.json()["data"]}
    assert names == {"Alice Host"}


# --- Permission catalog ------------------------------------------------------


async def _company_wide_user(db_session: AsyncSession, tenant: Tenant, *, codes: list[str]) -> User:
    """A fresh company-wide user granted exactly `codes` — used instead of
    the shared `user` fixture where the test needs a permission (e.g.
    `roles:view`) that fixture's `ADMIN_PERMISSION_CODES` doesn't include.
    """
    permissions = [Permission(id=uuid.uuid4(), code=code, description=code) for code in codes]
    role = RoleFactory.build(
        id=uuid.uuid4(), name=f"role-{uuid.uuid4().hex[:8]}", permissions=permissions
    )
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"perm-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name="Permission Test User",
        branch_roles=[branch_role],
    )
    db_session.add_all([*permissions, role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def test_list_permissions_success(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token: Callable[[User], str],
) -> None:
    viewer = await _company_wide_user(db_session, tenant, codes=["roles:view"])
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/auth/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()["data"]}
    assert "roles:view" in codes


async def test_list_permissions_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/auth/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


# --- Role CRUD --------------------------------------------------------------


async def test_create_role_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles",
        json={
            "name": "Security Admin",
            "description": "Manages security gates",
            "permissionCodes": ["branches:view"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == "Security Admin"
    assert body["permissionCodes"] == ["branches:view"]
    assert body["isStandard"] is False


async def test_create_role_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Security Admin", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_create_role_duplicate_name_conflict(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/roles", json={"name": "Ops Lead", "permissionCodes": []}, headers=headers
    )
    response = await client.post(
        "/api/v1/auth/roles", json={"name": "ops lead", "permissionCodes": []}, headers=headers
    )
    assert response.status_code == 409


async def test_create_role_unknown_permission_code_not_found(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Bogus Role", "permissionCodes": ["not-a-real-code"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_list_roles_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.get("/api/v1/auth/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_list_roles_includes_standard_and_custom(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/roles", json={"name": "Custom Role", "permissionCodes": []}, headers=headers
    )
    response = await client.get("/api/v1/auth/roles?pageSize=100", headers=headers)
    assert response.status_code == 200
    names = {r["name"] for r in response.json()["data"]}
    assert "admin" in names
    assert "Custom Role" in names


async def test_list_roles_pagination(client: AsyncClient, user: User) -> None:
    """Exercises actual page slicing and the envelope's pagination metadata
    (api-conventions.md §1) — `test_list_roles_includes_standard_and_custom`
    above only checks that a large `pageSize` returns everything, not that
    paging itself works.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    for name in ("Pager Role A", "Pager Role B", "Pager Role C"):
        await client.post(
            "/api/v1/auth/roles", json={"name": name, "permissionCodes": []}, headers=headers
        )

    first_page = await client.get("/api/v1/auth/roles?page=1&pageSize=2", headers=headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    pagination = first_body["pagination"]
    assert pagination["page"] == 1
    assert pagination["pageSize"] == 2
    # "admin" (seeded by the `user` fixture) plus the three roles just created.
    assert pagination["total"] >= 4
    assert pagination["totalPages"] >= 2
    assert len(first_body["data"]) == 2

    second_page = await client.get("/api/v1/auth/roles?page=2&pageSize=2", headers=headers)
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert second_body["pagination"]["page"] == 2
    assert len(second_body["data"]) >= 1

    first_ids = {r["id"] for r in first_body["data"]}
    second_ids = {r["id"] for r in second_body["data"]}
    assert first_ids.isdisjoint(second_ids)


async def test_get_role_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/auth/roles", json={"name": "Getter Role", "permissionCodes": []}, headers=headers
    )
    role_id = created.json()["data"]["id"]
    response = await client.get(f"/api/v1/auth/roles/{role_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Getter Role"


async def test_get_role_requires_permission(
    client: AsyncClient, user: User, user_without_permissions: User
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = await _login(client, user_without_permissions.email)
    response = await client.get(
        f"/api/v1/auth/roles/{role_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403


async def test_get_role_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        f"/api/v1/auth/roles/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_update_role_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Updatable Role", "permissionCodes": ["branches:view"]},
        headers=headers,
    )
    role_id = created.json()["data"]["id"]
    response = await client.put(
        f"/api/v1/auth/roles/{role_id}",
        json={"description": "Updated description", "permissionCodes": []},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["description"] == "Updated description"
    assert body["permissionCodes"] == []


async def test_update_role_requires_permission(
    client: AsyncClient, user: User, user_without_permissions: User
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Update-Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = await _login(client, user_without_permissions.email)
    response = await client.put(
        f"/api/v1/auth/roles/{role_id}",
        json={"description": "Should not be allowed"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403


async def test_update_role_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.put(
        f"/api/v1/auth/roles/{uuid.uuid4()}",
        json={"description": "Doesn't matter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_role_success(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Deletable Role", "permissionCodes": []},
        headers=headers,
    )
    role_id = created.json()["data"]["id"]
    response = await client.delete(f"/api/v1/auth/roles/{role_id}", headers=headers)
    assert response.status_code == 204
    get_response = await client.get(f"/api/v1/auth/roles/{role_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_role_requires_permission(
    client: AsyncClient, user: User, user_without_permissions: User
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Delete-Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = await _login(client, user_without_permissions.email)
    response = await client.delete(
        f"/api/v1/auth/roles/{role_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403


async def test_delete_role_not_found(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/auth/roles/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


async def test_verify_role_name_availability(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    available = await client.get("/api/v1/auth/roles/verify?name=Brand New Role", headers=headers)
    assert available.status_code == 200
    assert available.json()["data"]["available"] is True

    await client.post(
        "/api/v1/auth/roles", json={"name": "Taken Role", "permissionCodes": []}, headers=headers
    )
    taken = await client.get("/api/v1/auth/roles/verify?name=taken role", headers=headers)
    assert taken.status_code == 200
    assert taken.json()["data"]["available"] is False


async def test_verify_role_name_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.get(
        "/api/v1/auth/roles/verify?name=Whatever",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_rename_standard_role_rejected(client: AsyncClient, user: User) -> None:
    """The `user` fixture seeds a role literally named "admin" — standing in
    for one of the five seeded standard roles (`rbac_catalog.STANDARD_ROLE_NAMES`)
    without needing the full provisioning-time seed to run.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    list_response = await client.get("/api/v1/auth/roles?pageSize=100", headers=headers)
    admin_role = next(r for r in list_response.json()["data"] if r["name"] == "admin")
    response = await client.put(
        f"/api/v1/auth/roles/{admin_role['id']}",
        json={"name": "renamed-admin"},
        headers=headers,
    )
    assert response.status_code == 409


async def test_delete_standard_role_rejected(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    list_response = await client.get("/api/v1/auth/roles?pageSize=100", headers=headers)
    admin_role = next(r for r in list_response.json()["data"] if r["name"] == "admin")
    response = await client.delete(f"/api/v1/auth/roles/{admin_role['id']}", headers=headers)
    assert response.status_code == 409


async def test_delete_role_with_active_grant_conflict(
    client: AsyncClient, user: User, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Grantable Role", "permissionCodes": []},
        headers=headers,
    )
    role_id = created.json()["data"]["id"]
    assign_response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": role_id, "branchId": str(branch.id)},
        headers=headers,
    )
    assert assign_response.status_code == 201

    response = await client.delete(f"/api/v1/auth/roles/{role_id}", headers=headers)
    assert response.status_code == 409


# --- Resync standard roles against the catalog (add-invitation-approval-flow-and-role-resync) ---


async def test_resync_role_permissions_backfills_stale_role(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """Simulates the exact bug `rbac_catalog.py::seed_default_roles`'s own
    docstring describes: a role seeded before a permission existed in the
    catalog. `invitations:view` is stripped from `reception` after an
    initial seeding to stand in for that stale state.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    reception.permissions = [p for p in reception.permissions if p.code != "invitations:view"]
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    granted = {
        entry["roleName"]: entry["grantedPermissionCodes"] for entry in response.json()["data"]
    }
    assert "invitations:view" in granted["reception"]

    await db_session.refresh(reception)
    assert "invitations:view" in {p.code for p in reception.permissions}


async def test_resync_role_permissions_is_idempotent(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    await seed_default_roles(db_session)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.post("/api/v1/auth/roles/resync-permissions", headers=headers)
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/roles/resync-permissions", headers=headers)
    assert second.status_code == 200
    for entry in second.json()["data"]:
        assert entry["grantedPermissionCodes"] == []


async def test_resync_role_permissions_preserves_custom_grant(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """A permission a standard role holds outside its catalog-default set
    (granted by hand, e.g. via `PUT /auth/roles/{id}`) must survive the
    resync — it's additive-only, never a revoke.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    security = await RoleRepository(db_session).get_by_name("security")
    assert security is not None
    # `seed_default_roles` already inserted every catalog permission into
    # `global.permissions` (granted to some role or none) — fetch the
    # existing row for "security"'s extra grant rather than inserting a
    # second one with the same code.
    extra = (
        await db_session.execute(select(Permission).where(Permission.code == "invitations:approve"))
    ).scalar_one()
    if extra.code not in {p.code for p in security.permissions}:
        security.permissions.append(extra)
        await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    await db_session.refresh(security)
    assert "invitations:approve" in {p.code for p in security.permissions}


async def test_resync_role_permissions_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_role_repository_tenant_schema_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name="isolated-role", permissions=[])
    db_session.add(role)
    await db_session.commit()

    other_schema = "tenant_other_test_role"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await RoleRepository(other_session).get(role.id)
        assert found is None


# --- Branch-role revocation ---------------------------------------------


async def test_revoke_branch_role_removes_access(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    user_without_permissions: User,
    branch: Branch,
    issue_token: Callable[[User], str],
) -> None:
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="reception-revoke", permissions=[existing])
    db_session.add(role)
    await db_session.commit()

    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    assign_response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": str(branch.id)},
        headers=headers,
    )
    assignment_id = assign_response.json()["data"]["id"]

    revoke_response = await client.delete(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles/{assignment_id}",
        headers=headers,
    )
    assert revoke_response.status_code == 204

    db_session.expire(user_without_permissions, ["branch_roles"])
    granted_token = issue_token(user_without_permissions)
    current = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {granted_token}", "X-Branch-ID": str(branch.id)},
    )
    assert current.status_code == 403


async def test_revoke_branch_role_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.delete(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_revoke_branch_role_not_found(
    client: AsyncClient, user: User, user_without_permissions: User
) -> None:
    token = await _login(client, user.email)
    response = await client.delete(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Logout (API-19, audit-only — no token revocation) ------------------------


async def test_logout_writes_audit_entry(
    client: AsyncClient, db_session: AsyncSession, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text

    audit_stmt = select(AuditLog).where(
        AuditLog.actor_user_id == user.id, AuditLog.action == "logout"
    )
    entries = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(entries) == 1


async def test_logout_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401
