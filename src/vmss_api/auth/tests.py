import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BuildingFactory, DepartmentFactory, FloorFactory, RoleFactory
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.auth.repository import UserRepository
from vmss_api.core.rate_limit import limiter
from vmss_api.org_structure.models import Branch, Department


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
    assert {"roleName": "admin", "branchId": None} in body["branchRoles"]


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
    client: AsyncClient, user_without_permissions: User
) -> None:
    """Also asserts the response body shape: `HTTPException`s raised across
    the app (401/403/404/409/...) go through `core/middleware.py`'s
    `http_exception_handler`, so a 403 here is the same
    `{success, message, errors}` envelope every other response uses — not
    FastAPI's default `{"detail": ...}` body. See security-architecture.md §1.
    """
    token = await _login(client, user_without_permissions.email)
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

    granted_token = await _login(client, user_without_permissions.email)
    current = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {granted_token}", "X-Branch-ID": str(branch.id)},
    )
    assert current.status_code == 200


async def test_assign_branch_role_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
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
    department = DepartmentFactory.build(id=uuid.uuid4(), floor_id=floor.id, code="ENG")
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


async def test_sync_employee_directory_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
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


async def test_list_employees_requires_branch_header(client: AsyncClient, user: User) -> None:
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


async def test_list_employees_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.get(
        "/api/v1/auth/employees",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403
