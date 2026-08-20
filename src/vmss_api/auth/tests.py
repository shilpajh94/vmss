import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factories import BuildingFactory, DepartmentFactory, FloorFactory, RoleFactory, UserFactory
from vmss_api.auth.models import Permission, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.core.rate_limit import limiter
from vmss_api.core.security import hash_password
from vmss_api.org_structure.models import Branch, Department
from vmss_api.platform.models import TenantUserIndex
from vmss_api.tenant.models import Tenant


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
    """`user` is a company-wide Admin (branch_id=None grant) — omitting
    `X-Branch-ID` on a list request now scopes to every branch it's
    authorized for, per the auth spec's optional-header requirement.
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
    assert body["data"][0]["email"] == "erin@acme-test.example"


async def test_list_employees_without_branch_header_excludes_other_branches(
    client: AsyncClient, db_session: AsyncSession, user: User, tenant: Tenant, branch: Branch
) -> None:
    """A caller scoped to only one branch, with no `X-Branch-ID` header,
    must never see another branch's employees — the tenant/branch-isolation
    case testing-standards.md §2 requires for this change.
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
    viewer_token = await _login(client, viewer.email)
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()["data"]}
    assert emails == {"own-branch@acme-test.example"}


async def test_list_employees_requires_permission(
    client: AsyncClient, user_without_permissions: User, branch: Branch
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.get(
        "/api/v1/auth/employees",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 403


async def test_list_employees_without_branch_header_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.get(
        "/api/v1/auth/employees", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


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
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    viewer = await _company_wide_user(db_session, tenant, codes=["roles:view"])
    token = await _login(client, viewer.email)
    response = await client.get(
        "/api/v1/auth/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()["data"]}
    assert "roles:view" in codes


async def test_list_permissions_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
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
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
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
    granted_token = await _login(client, user_without_permissions.email)
    current = await client.get(
        "/api/v1/branches/current",
        headers={"Authorization": f"Bearer {granted_token}", "X-Branch-ID": str(branch.id)},
    )
    assert current.status_code == 403


async def test_revoke_branch_role_requires_permission(
    client: AsyncClient, user_without_permissions: User
) -> None:
    token = await _login(client, user_without_permissions.email)
    response = await client.delete(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
