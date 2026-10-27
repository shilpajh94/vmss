import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from factories import (
    BranchFactory,
    BuildingFactory,
    DepartmentFactory,
    FloorFactory,
    RoleFactory,
    UserFactory,
)
from vmss_api.auth.models import AuditLog, Permission, Role, User, UserBranchRole
from vmss_api.auth.rbac_catalog import seed_default_roles
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.auth.schemas import EmployeeCreateRequest
from vmss_api.auth.service import create_employee, resync_role_permissions
from vmss_api.core import storage
from vmss_api.core.config import settings
from vmss_api.core.rate_limit import limiter
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import hash_password, verify_password
from vmss_api.core.tenancy import get_current_user
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


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


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


# --- POST /auth/me/avatar (add-avatar-upload-and-verify-image-storage) -------


async def test_upload_avatar_success_and_fetchable_from_profile(
    client: AsyncClient, user: User
) -> None:
    """specs/auth/spec.md "Valid avatar upload succeeds and is retrievable"."""
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    photo_bytes = _jpeg_bytes()

    upload_response = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("avatar.jpg", photo_bytes, "image/jpeg")},
        headers=headers,
    )
    assert upload_response.status_code == 200, upload_response.text
    avatar_url = upload_response.json()["data"]["avatarUrl"]
    assert avatar_url is not None

    profile_response = await client.get("/api/v1/auth/me", headers=headers)
    assert profile_response.json()["data"]["avatarUrl"] == avatar_url

    fetched = await client.get(avatar_url)
    assert fetched.status_code == 200
    assert fetched.content == photo_bytes


async def test_upload_avatar_disguised_content_rejected(client: AsyncClient, user: User) -> None:
    """specs/auth/spec.md "Disguised executable submitted as an avatar is
    rejected" — the user's existing avatar (if any) is left unchanged.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    first_upload = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("avatar.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    original_avatar_url = first_upload.json()["data"]["avatarUrl"]

    disguised_response = await client.post(
        "/api/v1/auth/me/avatar",
        files={
            "file": (
                "avatar.jpg",
                b"this is not actually an image, just plain text bytes",
                "image/jpeg",
            )
        },
        headers=headers,
    )
    assert disguised_response.status_code == 422

    profile_response = await client.get("/api/v1/auth/me", headers=headers)
    assert profile_response.json()["data"]["avatarUrl"] == original_avatar_url


async def test_upload_avatar_oversized_rejected(
    client: AsyncClient, user: User, monkeypatch
) -> None:
    """specs/auth/spec.md "Oversized avatar upload is rejected" — rejected
    before the full upload is buffered into memory
    (add-avatar-upload-and-verify-image-storage/design.md Decision 3).
    """
    monkeypatch.setattr(settings, "avatar_max_upload_size_bytes", 10)
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("avatar.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 422

    profile_response = await client.get("/api/v1/auth/me", headers=headers)
    assert profile_response.json()["data"]["avatarUrl"] is None


async def test_upload_avatar_replaces_previous(client: AsyncClient, user: User) -> None:
    """specs/auth/spec.md "Uploading a new avatar replaces the previous
    one".
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    first_upload = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("first.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    first_avatar_url = first_upload.json()["data"]["avatarUrl"]

    second_photo = io.BytesIO()
    Image.new("RGB", (3, 3), color="black").save(second_photo, format="PNG")
    second_upload = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("second.png", second_photo.getvalue(), "image/png")},
        headers=headers,
    )
    second_avatar_url = second_upload.json()["data"]["avatarUrl"]
    assert second_avatar_url != first_avatar_url

    profile_response = await client.get("/api/v1/auth/me", headers=headers)
    assert profile_response.json()["data"]["avatarUrl"] == second_avatar_url


async def test_user_with_no_avatar_returns_null_avatar_url(client: AsyncClient, user: User) -> None:
    """specs/auth/spec.md "A user with no avatar uploaded has no avatar
    URL".
    """
    token = await _login(client, user.email)
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["avatarUrl"] is None


async def test_upload_avatar_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("avatar.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 401


async def test_list_employees_surfaces_uploaded_avatar_url(client: AsyncClient, user: User) -> None:
    """`GET /auth/employees` (`EmployeeOut`) already had an `avatarUrl`
    field — confirms it's actually populated end to end once an avatar
    exists, not just present-but-always-null.
    """
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    upload_response = await client.post(
        "/api/v1/auth/me/avatar",
        files={"file": ("avatar.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    avatar_url = upload_response.json()["data"]["avatarUrl"]

    response = await client.get("/api/v1/auth/employees", headers=headers)
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["email"] == user.email)
    assert row["avatarUrl"] == avatar_url


async def test_employee_directory_surfaces_avatar_url(
    db_session: AsyncSession, tenant: Tenant, client: AsyncClient
) -> None:
    """specs/auth/spec.md "Employee directory listing surfaces the same
    avatar field as other employee listings" — `EmployeeDirectoryOut` used
    to omit `avatarUrl` entirely, unlike `EmployeeOut`.
    """
    photo_key = await storage.save(tenant.id, "auth/avatars", _jpeg_bytes(), "image/jpeg")
    host_role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(host_role)
    await db_session.commit()
    host_user = await _make_role_user(
        db_session, tenant, host_role, email="dana@acme-test.example", full_name="Dana Host"
    )
    host_user.avatar_url = photo_key
    await db_session.commit()

    response = await client.get("/api/v1/auth/employees/directory")
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["fullName"] == "Dana Host")
    assert row["avatarUrl"] is not None

    fetched = await client.get(row["avatarUrl"])
    assert fetched.status_code == 200


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


async def test_get_by_email_tenant_schema_isolation(
    user: User, make_tenant_schema, open_tenant_session
) -> None:
    """`UserRepository.get_by_email` backs `POST /auth/users`'s
    already-registered-email check — see testing-standards.md §2.
    """
    other_schema = "tenant_other_test_user_email"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await UserRepository(other_session).get_by_email(user.email)
        assert found is None


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


async def test_assign_branch_role_duplicate_grant_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    user_without_permissions: User,
    branch: Branch,
) -> None:
    """Regression test: a second identical grant used to raise an unhandled
    `IntegrityError` (the DB's `uq_user_branch_role` constraint) instead of
    a clean 409 — see codebase-review-and-e2e-scenario-test.
    """
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="reception-duplicate", permissions=[existing])
    db_session.add(role)
    await db_session.commit()

    # Captured before the requests below: the service's `IntegrityError`
    # rollback on the second request expires every object already loaded in
    # this shared `db_session` (the `client` fixture routes `get_db`/
    # `get_tenant_db` through it), so touching `.id` on these fixtures
    # afterward would trigger an out-of-greenlet-context lazy refresh.
    target_user_id, role_id, branch_id = user_without_permissions.id, role.id, branch.id
    token = await _login(client, user.email)
    payload = {"roleId": str(role_id), "branchId": str(branch_id)}
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        f"/api/v1/auth/users/{target_user_id}/branch-roles",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/auth/users/{target_user_id}/branch-roles",
        json=payload,
        headers=headers,
    )
    assert second.status_code == 409

    count = await db_session.execute(
        select(func.count())
        .select_from(UserBranchRole)
        .where(
            UserBranchRole.user_id == target_user_id,
            UserBranchRole.role_id == role_id,
            UserBranchRole.branch_id == branch_id,
        )
    )
    assert count.scalar_one() == 1


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


async def test_assign_branch_role_soft_deleted_role_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    user: User,
    user_without_permissions: User,
    branch: Branch,
) -> None:
    """A soft-deleted role is invisible to normal lookups, same as one that
    never existed — see harden-referential-integrity-and-rbac-gates.
    """
    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(id=uuid.uuid4(), name="reception-soft-deleted", permissions=[existing])
    db_session.add(role)
    await db_session.flush()
    await db_session.execute(
        update(Role).where(Role.id == role.id).values(deleted_at=datetime.now(UTC))
    )
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": str(branch.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_assign_branch_role_soft_deleted_branch_not_found(
    client: AsyncClient, db_session: AsyncSession, user: User, user_without_permissions: User
) -> None:
    branch = Branch(id=uuid.uuid4(), name="Soft Deleted Branch", code="SOFT-DEL")
    db_session.add(branch)
    await db_session.flush()
    await db_session.execute(
        update(Branch).where(Branch.id == branch.id).values(deleted_at=datetime.now(UTC))
    )

    existing = (
        await db_session.execute(select(Permission).where(Permission.code == "branches:view"))
    ).scalar_one()
    role = RoleFactory.build(
        id=uuid.uuid4(), name="reception-soft-deleted-branch", permissions=[existing]
    )
    db_session.add(role)
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        f"/api/v1/auth/users/{user_without_permissions.id}/branch-roles",
        json={"roleId": str(role.id), "branchId": str(branch.id)},
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


async def test_get_by_emails_and_deactivate_employees_not_in_tenant_schema_isolation(
    db_session: AsyncSession, make_tenant_schema, open_tenant_session
) -> None:
    """`UserRepository.get_by_emails`/`.deactivate_employees_not_in` back
    `POST /auth/employees/sync`'s batch reconciliation — see
    testing-standards.md §2.
    """
    employee = UserFactory.build(
        id=uuid.uuid4(),
        email="isolated-employee@acme-test.example",
        employee_code="ISO-EMP-1",
    )
    db_session.add(employee)
    await db_session.commit()

    other_schema = "tenant_other_test_employee_batch"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await UserRepository(other_session).get_by_emails([employee.email])
        assert found == []

        deactivated = await UserRepository(other_session).deactivate_employees_not_in([])
        assert deactivated == []

    await db_session.refresh(employee)
    assert employee.is_active is True


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


async def test_create_employee_with_password_stores_usable_hash(
    db_session: AsyncSession, tenant: Tenant, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    base = {"full_name": "Pw Employee", "department_id": department.id}
    with_pw = await create_employee(
        db_session,
        tenant_id=tenant.id,
        payload=EmployeeCreateRequest(
            email="pw-emp@acme-test.example",
            employee_code="EMP-PW1",
            password="Pass@1234",
            **base,
        ),
    )
    assert verify_password("Pass@1234", with_pw.hashed_password)

    without_pw = await create_employee(
        db_session,
        tenant_id=tenant.id,
        payload=EmployeeCreateRequest(
            email="nopw@acme-test.example", employee_code="EMP-PW2", **base
        ),
    )
    assert not verify_password("Pass@1234", without_pw.hashed_password)


async def test_create_employee_rejects_short_password(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/employees",
        json={
            "email": "short@acme-test.example",
            "fullName": "Short",
            "employeeCode": "EMP-SH1",
            "departmentId": str(department.id),
            "password": "abc",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


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
    client: AsyncClient,
    user_without_permissions: User,
    branch: Branch,
    db_session: AsyncSession,
    issue_token: Callable[[User], str],
) -> None:
    department = await _make_department(db_session, branch)
    token = issue_token(user_without_permissions)
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


async def test_list_employees_with_branch_header_includes_employee_with_no_department(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    """A departmentless employee with no branch-scoped role grant belongs to
    every branch, so a branch-scoped listing includes them (see
    `UserRepository.list_employees_page`). They'd previously been
    invisible from any `X-Branch-ID`-scoped call, including the approval
    delegate-candidate lookup.
    """
    branch_id = branch.id  # a request rolls back the shared session, expiring fixtures
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
        "/api/v1/auth/employees", headers={**headers, "X-Branch-ID": str(branch_id)}
    )
    assert response.status_code == 200
    names = {e["fullName"] for e in response.json()["data"]}
    assert "Dana Employee" in names


async def _make_role_holder_no_department(
    db_session: AsyncSession, tenant: Tenant, role_name: str, branch_id: uuid.UUID | None
) -> User:
    role = RoleFactory.build(id=uuid.uuid4(), name=role_name, permissions=[])
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=branch_id)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{role_name}-{uuid.uuid4().hex[:8]}@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name=f"{role_name.title()} No Department",
        branch_roles=[branch_role],
    )
    db_session.add_all([role, test_user])
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()
    return test_user


async def test_list_employees_with_branch_header_includes_departmentless_matching_branch_role(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User, branch: Branch
) -> None:
    """A user with no `department_id` still appears in a branch-scoped
    listing when their own `UserBranchRole` is scoped to that exact branch
    — the RBAC branch grant is itself sufficient to place them there, not
    only their (optional) department. Complements
    `test_list_employees_with_branch_header_includes_employee_with_no_department`,
    whose departmentless user has no role grant at all.
    """
    role_holder = await _make_role_holder_no_department(db_session, tenant, "host", branch.id)

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/employees",
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    emails = {e["email"] for e in response.json()["data"]}
    assert role_holder.email in emails


async def test_list_employees_with_branch_header_includes_departmentless_all_branch_role_holder(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User, branch: Branch
) -> None:
    """An "All Branch" (`branch_id=None`, company-wide) role grant makes a
    departmentless user visible in *every* branch-scoped listing, not just
    an unscoped one — the same "company-wide means every branch" rule
    `auth/models.py::User.has_branch_access` already applies to permission
    checks now also applies to this listing. Closes the gap where an
    All-Branch host was invisible from a `?role=host&X-Branch-ID=...`
    delegate-candidate lookup.
    """
    role_holder = await _make_role_holder_no_department(db_session, tenant, "host", None)

    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/employees",
        params={"role": "host"},
        headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)},
    )
    assert response.status_code == 200
    emails = {e["email"] for e in response.json()["data"]}
    assert role_holder.email in emails


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


async def test_list_employees_filter_by_status(
    db_session: AsyncSession, client: AsyncClient, tenant: Tenant
) -> None:
    active_employee = UserFactory.build(
        id=uuid.uuid4(), email="active-emp@acme-test.example", is_active=True
    )
    inactive_employee = UserFactory.build(
        id=uuid.uuid4(), email="inactive-emp@acme-test.example", is_active=False
    )
    db_session.add_all([active_employee, inactive_employee])
    await db_session.commit()

    response = await client.get("/api/v1/auth/employees?status=inactive")
    assert response.status_code == 200
    emails = {e["email"] for e in response.json()["data"]}
    assert inactive_employee.email in emails
    assert active_employee.email not in emails


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


async def test_list_employee_directory_sort_by_name(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    """verify-full-api-test-and-validation-coverage task 7.2/7.4 — the
    `sortBy`/`sortOrder` params on `GET /auth/employees/directory`
    (`auth/router.py::list_employee_directory`) are additive-only per
    `api-conventions.md` §2, but had no HTTP-level test proving they
    actually reorder the response (`UserRepository.list_hosts_page`'s
    tenant-isolation test at line ~1491 exercises the same params but not
    through the endpoint, and doesn't assert ordering).
    """
    host_role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(host_role)
    await db_session.commit()
    await _make_role_user(
        db_session, tenant, host_role, email="zed@acme-test.example", full_name="Zed Host"
    )
    await _make_role_user(
        db_session, tenant, host_role, email="anna@acme-test.example", full_name="Anna Host"
    )

    asc_response = await client.get(
        "/api/v1/auth/employees/directory", params={"sortBy": "name", "sortOrder": "asc"}
    )
    asc_names = [e["fullName"] for e in asc_response.json()["data"]]
    assert asc_names.index("Anna Host") < asc_names.index("Zed Host")

    desc_response = await client.get(
        "/api/v1/auth/employees/directory", params={"sortBy": "name", "sortOrder": "desc"}
    )
    desc_names = [e["fullName"] for e in desc_response.json()["data"]]
    assert desc_names.index("Anna Host") > desc_names.index("Zed Host")


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


async def test_list_hosts_page_tenant_schema_isolation(
    db_session: AsyncSession, tenant: Tenant, make_tenant_schema, open_tenant_session
) -> None:
    """`UserRepository.list_hosts_page` backs `GET /auth/employees/directory`
    — see testing-standards.md §2.
    """
    host_role = RoleFactory.build(id=uuid.uuid4(), name="host", permissions=[])
    db_session.add(host_role)
    await db_session.commit()
    await _make_role_user(
        db_session,
        tenant,
        host_role,
        email="isolated-host@acme-test.example",
        full_name="Isolated Host",
    )

    other_schema = "tenant_other_test_hosts"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        hosts, total = await UserRepository(other_session).list_hosts_page(
            page=1, page_size=100, sort_by="name", sort_order=SortOrder.asc
        )
        assert hosts == []
        assert total == 0


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
        "/api/v1/auth/permissions?pageSize=100", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    codes = {row["code"] for row in body["data"]}
    assert "roles:view" in codes
    assert body["pagination"]["total"] == len(codes)


async def test_list_permissions_requires_permission(
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/auth/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def _synthetic_permission_codes(count: int) -> list[str]:
    """Deterministic, lexically-orderable codes for pagination/sort tests —
    `_company_wide_user` inserts exactly these into the (test-isolated)
    global `permissions` table, so the catalog's size for these tests is
    fully controlled rather than relying on however many rows
    `rbac_catalog.PERMISSION_CODES` happens to seed.
    """
    return [f"synthetic-perm:{i:03d}" for i in range(count)]


async def test_list_permissions_default_page(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token: Callable[[User], str],
) -> None:
    """No `page`/`pageSize` supplied SHALL return page 1 at the house
    default page size, with a correct `total`/`totalPages` for the full
    catalog — see openspec/specs/auth/spec.md's "Permission catalog is
    paginated" scenario.
    """
    codes = ["roles:view", *_synthetic_permission_codes(24)]
    viewer = await _company_wide_user(db_session, tenant, codes=codes)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/auth/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["pageSize"] == 20
    assert len(body["data"]) == 20
    assert body["pagination"]["total"] == len(codes)
    assert body["pagination"]["totalPages"] == 2


async def test_list_permissions_page_beyond_last_is_empty(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token: Callable[[User], str],
) -> None:
    """A `page` past the catalog's last page SHALL return an empty `data`
    array with a valid pagination block, not a 404/400 — see
    openspec/specs/auth/spec.md's "page beyond the last page is empty, not
    an error" scenario.
    """
    viewer = await _company_wide_user(
        db_session, tenant, codes=["roles:view", *_synthetic_permission_codes(3)]
    )
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/auth/permissions?page=9999&pageSize=20",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["page"] == 9999


async def test_list_permissions_sort_desc(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token: Callable[[User], str],
) -> None:
    codes = ["roles:view", *_synthetic_permission_codes(5)]
    viewer = await _company_wide_user(db_session, tenant, codes=codes)
    token = issue_token(viewer)
    response = await client.get(
        "/api/v1/auth/permissions?pageSize=100&sortBy=code&sortOrder=desc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    returned = [row["code"] for row in response.json()["data"] if row["code"] in codes]
    assert returned == sorted(codes, reverse=True)


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
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get("/api/v1/auth/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.parametrize("role_name", ["reception", "host"])
async def test_list_roles_reception_and_host_can_view(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    issue_token: Callable[[User], str],
    role_name: str,
) -> None:
    """Reception and Host both carry `roles:view` in the standard catalog
    (`rbac_catalog.py::ROLE_PERMISSIONS`) specifically so their portal/app
    UI can resolve role data for the approve/delegate actions on an
    invitation — without it, `GET /auth/roles` 403s for these roles and the
    UI has no permission data to decide whether to render those buttons.
    Seeds from the real catalog (not a hand-picked permission list) so this
    test breaks if `roles:view` is ever dropped from either role.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    role = await RoleRepository(db_session).get_by_name(role_name)
    assert role is not None
    branch_role = UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)
    test_user = UserFactory.build(
        id=uuid.uuid4(),
        email=f"{role_name}-roles-view@acme-test.example",
        hashed_password=hash_password("correct-password"),
        full_name=f"{role_name.title()} User",
        branch_roles=[branch_role],
    )
    db_session.add(test_user)
    await db_session.flush()
    db_session.add(
        TenantUserIndex(email=test_user.email, tenant_id=tenant.id, user_id=test_user.id)
    )
    await db_session.commit()

    token = issue_token(test_user)
    response = await client.get("/api/v1/auth/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


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


async def test_role_list_page_tenant_schema_isolation(
    db_session: AsyncSession, make_tenant_schema, open_tenant_session
) -> None:
    """`RoleRepository.list_page` backs `GET /auth/roles` — see
    testing-standards.md §2.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="Listed Role", permissions=[])
    db_session.add(role)
    await db_session.commit()

    other_schema = "tenant_other_test_role_list"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        roles, total = await RoleRepository(other_session).list_page(
            page=1, page_size=100, sort_by="name", sort_order=SortOrder.asc
        )
        assert roles == []
        assert total == 0


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
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = issue_token(user_without_permissions)
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
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Update-Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = issue_token(user_without_permissions)
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
    client: AsyncClient,
    user: User,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
) -> None:
    token = await _login(client, user.email)
    created = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Delete-Gate-Checked Role", "permissionCodes": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    role_id = created.json()["data"]["id"]

    other_token = issue_token(user_without_permissions)
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
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.get(
        "/api/v1/auth/roles/verify?name=Whatever",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_by_name_case_insensitive_tenant_schema_isolation(
    db_session: AsyncSession, make_tenant_schema, open_tenant_session
) -> None:
    """`RoleRepository.get_by_name_case_insensitive` backs `POST /auth/roles`
    and `GET /auth/roles/verify` — see testing-standards.md §2.
    """
    role = RoleFactory.build(id=uuid.uuid4(), name="Isolated Role", permissions=[])
    db_session.add(role)
    await db_session.commit()

    other_schema = "tenant_other_test_role_name"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await RoleRepository(other_session).get_by_name_case_insensitive("isolated role")
        assert found is None


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


# --- Field-length validation hardening (verify-full-api-test-and-validation-coverage) ---


async def test_login_password_exceeds_max_length_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "whoever@acme-test.example", "password": "x" * 129},
    )
    assert response.status_code == 422


async def test_create_user_password_exceeds_max_length_rejected(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "over-length@acme-test.example",
            "password": "x" * 129,
            "fullName": "Over Length",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_create_role_permission_code_exceeds_max_length_rejected(
    client: AsyncClient, user: User
) -> None:
    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles",
        json={"name": "Over Length Codes", "permissionCodes": ["x" * 101]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


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


async def test_resync_role_permissions_backfills_documents_view(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """enrich-invitation-checkin-and-detail-views design.md Decision 6 —
    the resync endpoint is the rollout path for a tenant provisioned before
    `documents:view` existed in the catalog: it backfills the permission
    onto Reception and Security without a manual database edit.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    reception = await RoleRepository(db_session).get_by_name("reception")
    security = await RoleRepository(db_session).get_by_name("security")
    assert reception is not None
    assert security is not None
    reception.permissions = [p for p in reception.permissions if p.code != "documents:view"]
    security.permissions = [p for p in security.permissions if p.code != "documents:view"]
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    granted = {
        entry["roleName"]: entry["grantedPermissionCodes"] for entry in response.json()["data"]
    }
    assert "documents:view" in granted["reception"]
    assert "documents:view" in granted["security"]

    await db_session.refresh(reception)
    await db_session.refresh(security)
    assert "documents:view" in {p.code for p in reception.permissions}
    assert "documents:view" in {p.code for p in security.permissions}


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
    client: AsyncClient, user_without_permissions: User, issue_token: Callable[[User], str]
) -> None:
    token = issue_token(user_without_permissions)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_resync_role_permissions_tenant_schema_isolation(
    client: AsyncClient,
    user: User,
    db_session: AsyncSession,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    """`POST /auth/roles/resync-permissions`'s bulk `seed_default_roles`
    write path must only ever touch the tenant schema the caller's session is
    bound to — a role it creates/updates in that schema must not appear in a
    different tenant's schema. See testing-standards.md §2.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    reception.permissions = [p for p in reception.permissions if p.code != "invitations:view"]
    await db_session.commit()

    other_schema = "tenant_other_test_resync"
    await make_tenant_schema(other_schema)

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    async with open_tenant_session(other_schema) as other_session:
        found = await RoleRepository(other_session).get_by_name("reception")
        assert found is None


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


async def test_get_branch_role_assignment_tenant_schema_isolation(
    user: User, make_tenant_schema, open_tenant_session
) -> None:
    """`UserRepository.get_branch_role_assignment` backs
    `DELETE /auth/users/{id}/branch-roles/{id}` — see testing-standards.md §2.
    """
    assignment_id = user.branch_roles[0].id

    other_schema = "tenant_other_test_branch_role_assignment"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        found = await UserRepository(other_session).get_branch_role_assignment(
            user.id, assignment_id
        )
        assert found is None


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


async def test_get_current_user_tenant_schema_isolation(
    user: User, tenant: Tenant, make_tenant_schema, open_tenant_session
) -> None:
    """`get_current_user` (`core/tenancy.py`) issues its own raw
    `select(User)` against whatever session `get_tenant_db` resolves to —
    the dependency behind both `GET /auth/me` and `POST /auth/logout`. The
    `client` fixture routes every request's `get_tenant_db` through the one
    shared `db_session` regardless of the token's tenant claim
    (conftest.py's `client` fixture), so an HTTP-level test through `client`
    can't actually exercise cross-schema resolution here — this calls the
    dependency directly against a session bound to a *different* tenant's
    schema instead, the same way `invitations/tests.py` exercises a service
    function directly with `pytest.raises(HTTPException)`.
    """
    other_schema = "tenant_other_test_current_user"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                {"sub": str(user.id), "tenant_id": str(tenant.id)}, other_session
            )
        assert exc_info.value.status_code == 401


# --- list_user_ids_holding_role_at_branch (add-invitation-push-notifications) -


async def test_list_user_ids_holding_role_at_branch(
    db_session: AsyncSession, branch: Branch
) -> None:
    """New in add-invitation-push-notifications/design.md Decision 3 — the
    fan-out counterpart of `approvals/service.py::_user_holds_role_at_branch`'s
    single-user check: every holder of a role at a branch, company-wide
    grants (`branch_id IS NULL`) included, other branches excluded.
    """
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Other Branch", code="OTHER")
    role = RoleFactory.build(id=uuid.uuid4(), name="branch-scoped-role", permissions=[])
    branch_scoped_user = UserFactory.build(id=uuid.uuid4(), email="branch-scoped@acme-test.example")
    company_wide_user = UserFactory.build(id=uuid.uuid4(), email="company-wide@acme-test.example")
    other_branch_user = UserFactory.build(id=uuid.uuid4(), email="other-branch@acme-test.example")
    db_session.add_all(
        [other_branch, role, branch_scoped_user, company_wide_user, other_branch_user]
    )
    await db_session.flush()
    db_session.add_all(
        [
            UserBranchRole(
                id=uuid.uuid4(), user_id=branch_scoped_user.id, role_id=role.id, branch_id=branch.id
            ),
            UserBranchRole(
                id=uuid.uuid4(), user_id=company_wide_user.id, role_id=role.id, branch_id=None
            ),
            UserBranchRole(
                id=uuid.uuid4(),
                user_id=other_branch_user.id,
                role_id=role.id,
                branch_id=other_branch.id,
            ),
        ]
    )
    await db_session.commit()

    holders = await UserRepository(db_session).list_user_ids_holding_role_at_branch(
        role.id, branch.id
    )

    assert set(holders) == {branch_scoped_user.id, company_wide_user.id}
    assert other_branch_user.id not in holders


async def test_list_user_ids_holding_role_at_branch_tenant_isolation(
    make_tenant_schema, open_tenant_session, db_session: AsyncSession, branch: Branch
) -> None:
    role = RoleFactory.build(id=uuid.uuid4(), name="isolated-role", permissions=[])
    holder = UserFactory.build(id=uuid.uuid4(), email="isolated-holder@acme-test.example")
    db_session.add_all([role, holder])
    await db_session.flush()
    db_session.add(
        UserBranchRole(id=uuid.uuid4(), user_id=holder.id, role_id=role.id, branch_id=branch.id)
    )
    await db_session.commit()

    other_schema = "tenant_other_role_holders_test"
    await make_tenant_schema(other_schema)

    async with open_tenant_session(other_schema) as other_session:
        holders = await UserRepository(other_session).list_user_ids_holding_role_at_branch(
            role.id, branch.id
        )
        assert holders == []


# --- restrict-delegated-invitation-visibility ----------------------------------


async def test_seeded_roles_grant_invitations_view_all_to_branch_wide_roles_only(
    db_session: AsyncSession,
) -> None:
    """spec.md "A newly provisioned tenant's standard roles"."""
    await seed_default_roles(db_session)
    await db_session.commit()

    repo = RoleRepository(db_session)
    for name in ("admin", "reception", "security"):
        role = await repo.get_by_name(name)
        assert role is not None
        assert "invitations:view-all" in {p.code for p in role.permissions}, name
    host = await repo.get_by_name("host")
    assert host is not None
    host_codes = {p.code for p in host.permissions}
    assert "invitations:view" in host_codes
    assert "invitations:view-all" not in host_codes


async def test_permission_catalog_lists_invitations_view_all(
    client: AsyncClient, user: User
) -> None:
    """spec.md "The new permission is listed in the catalog"."""
    token = await _login(client, user.email)
    response = await client.get(
        "/api/v1/auth/permissions?pageSize=100", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "invitations:view-all" in {p["code"] for p in response.json()["data"]}


async def test_resync_role_permissions_backfills_invitations_view_all(
    client: AsyncClient, user: User, db_session: AsyncSession
) -> None:
    """The resync endpoint is one rollout path for existing tenants
    (restrict-delegated-invitation-visibility/design.md Migration Plan) —
    it backfills `invitations:view-all` onto a stale Reception role.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    reception.permissions = [p for p in reception.permissions if p.code != "invitations:view-all"]
    await db_session.commit()

    token = await _login(client, user.email)
    response = await client.post(
        "/api/v1/auth/roles/resync-permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    granted = {
        entry["roleName"]: entry["grantedPermissionCodes"] for entry in response.json()["data"]
    }
    assert "invitations:view-all" in granted["reception"]
    assert "invitations:view-all" not in granted.get("host", [])


# --- grant-reception-checkout-permission --------------------------------------


async def test_seeded_roles_grant_invitations_checkout_to_reception(
    db_session: AsyncSession,
) -> None:
    """spec.md "A newly provisioned tenant's Reception role can check visitors out"."""
    await seed_default_roles(db_session)
    await db_session.commit()

    repo = RoleRepository(db_session)
    for name in ("admin", "reception", "security"):
        role = await repo.get_by_name(name)
        assert role is not None
        assert "invitations:checkout" in {p.code for p in role.permissions}, name
    for name in ("host", "visitor"):
        role = await repo.get_by_name(name)
        assert role is not None
        assert "invitations:checkout" not in {p.code for p in role.permissions}, name


async def test_resync_role_permissions_backfills_reception_invitations_checkout(
    db_session: AsyncSession,
) -> None:
    """Service-level rather than via `POST /auth/roles/resync-permissions`:
    the endpoint-level resync tests currently fail under the shared test
    session (`get_tenant`'s `db.rollback()` expires the actor before the
    audit task reads `actor.id`), unrelated to the catalog itself.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    reception = await RoleRepository(db_session).get_by_name("reception")
    assert reception is not None
    reception.permissions = [p for p in reception.permissions if p.code != "invitations:checkout"]
    await db_session.commit()

    granted = await resync_role_permissions(db_session)
    assert "invitations:checkout" in granted["reception"]
    assert "invitations:checkout" not in granted.get("host", [])

    again = await resync_role_permissions(db_session)
    assert all("invitations:checkout" not in codes for codes in again.values())


# --- add-invitation-approval-revert --------------------------------------------


async def test_seeded_roles_grant_invitations_revert_approval_to_approving_roles(
    db_session: AsyncSession,
) -> None:
    """spec.md "A newly provisioned tenant's approving roles can revert"."""
    await seed_default_roles(db_session)
    await db_session.commit()

    repo = RoleRepository(db_session)
    for name in ("admin", "reception", "host"):
        role = await repo.get_by_name(name)
        assert role is not None
        assert "invitations:revert-approval" in {p.code for p in role.permissions}, name
    for name in ("security", "visitor"):
        role = await repo.get_by_name(name)
        assert role is not None
        assert "invitations:revert-approval" not in {p.code for p in role.permissions}, name


async def test_resync_role_permissions_backfills_invitations_revert_approval(
    db_session: AsyncSession,
) -> None:
    """Service-level for the same reason as
    `test_resync_role_permissions_backfills_reception_invitations_checkout`.
    """
    await seed_default_roles(db_session)
    await db_session.commit()

    repo = RoleRepository(db_session)
    for name in ("reception", "host"):
        role = await repo.get_by_name(name)
        assert role is not None
        role.permissions = [p for p in role.permissions if p.code != "invitations:revert-approval"]
    await db_session.commit()

    granted = await resync_role_permissions(db_session)
    assert "invitations:revert-approval" in granted["reception"]
    assert "invitations:revert-approval" in granted["host"]
    assert "invitations:revert-approval" not in granted.get("security", [])

    again = await resync_role_permissions(db_session)
    assert all("invitations:revert-approval" not in codes for codes in again.values())


# --- Admin disable / enable / delete of a single employee -----------------


async def _make_employee(
    db_session: AsyncSession,
    tenant: Tenant,
    *,
    email: str,
    employee_code: str | None = None,
    admin: bool = False,
) -> User:
    """A plain employee (or, with `admin=True`, a second company-wide Admin
    holding no permissions beyond the role name `has_admin_role` checks).
    """
    branch_roles = []
    if admin:
        role = await RoleRepository(db_session).get_by_name("admin")
        if role is None:
            role = RoleFactory.build(id=uuid.uuid4(), name="admin", permissions=[])
        branch_roles = [UserBranchRole(id=uuid.uuid4(), role=role, branch_id=None)]
    employee = UserFactory.build(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("correct-password"),
        full_name=email.split("@")[0].title(),
        employee_code=employee_code,
        is_active=True,
        disabled_by_admin=False,
        branch_roles=branch_roles,
    )
    db_session.add(employee)
    await db_session.flush()
    db_session.add(TenantUserIndex(email=email, tenant_id=tenant.id, user_id=employee.id))
    await db_session.commit()
    return employee


async def _audit_count(db_session: AsyncSession, action: str) -> int:
    stmt = select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    return (await db_session.execute(stmt)).scalar_one()


async def test_disable_employee_blocks_access_and_is_reversible(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    issue_token: Callable[[User], str],
) -> None:
    target = await _make_employee(
        db_session, tenant, email="dina@acme-test.example", employee_code="EMP-D1", admin=True
    )
    target_token = issue_token(target)
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    response = await client.post(f"/api/v1/auth/employees/{target.id}/disable", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["isActive"] is False

    # Existing session revoked, login rejected, excluded from host selection.
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {target_token}"})
    assert me.status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": "correct-password"}
    )
    assert login.status_code == 401
    repo = UserRepository(db_session)
    assert await repo.get_active(target.id) is None
    hosts = await repo.search_active_by_name_or_email("dina", limit=10)
    assert target.id not in {h.id for h in hosts}
    listing = await client.get("/api/v1/auth/employees?status=inactive&pageSize=100")
    assert target.email in {row["email"] for row in listing.json()["data"]}

    # Repeating the disable is a no-op: one audit entry only.
    again = await client.post(f"/api/v1/auth/employees/{target.id}/disable", headers=headers)
    assert again.status_code == 200
    assert await _audit_count(db_session, "employee_disabled") == 1

    enabled = await client.post(f"/api/v1/auth/employees/{target.id}/enable", headers=headers)
    assert enabled.status_code == 200
    assert enabled.json()["data"]["isActive"] is True
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {target_token}"})
    ).status_code == 200
    relogin = await client.post(
        "/api/v1/auth/login", json={"email": target.email, "password": "correct-password"}
    )
    assert relogin.status_code == 200
    # Enabling an already-enabled employee records nothing further.
    await client.post(f"/api/v1/auth/employees/{target.id}/enable", headers=headers)
    assert await _audit_count(db_session, "employee_enabled") == 1


async def test_delete_employee_releases_identifiers_and_keeps_row(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User, branch: Branch
) -> None:
    department = await _make_department(db_session, branch)
    department_id = department.id
    tenant_id = tenant.id  # a request's rollback expires the shared session's objects
    target = await _make_employee(
        db_session, tenant, email="erin@acme-test.example", employee_code="EMP-E1"
    )
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}

    response = await client.delete(f"/api/v1/auth/employees/{target.id}", headers=headers)
    assert response.status_code == 204

    listing = await client.get("/api/v1/auth/employees?pageSize=100")
    assert target.email not in {row["email"] for row in listing.json()["data"]}
    assert await UserRepository(db_session).get_by_email("erin@acme-test.example") is None
    assert await db_session.get(TenantUserIndex, "erin@acme-test.example") is None
    # Row retained for historical references, as a tombstone.
    await db_session.refresh(target)
    assert target.deleted_at is not None
    assert target.is_active is False
    assert target.employee_code is None
    assert target.email.endswith("@invalid.local")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "erin@acme-test.example", "password": "correct-password"},
    )
    assert login.status_code == 401

    # Email and code are reusable.
    recreated = await create_employee(
        db_session,
        tenant_id=tenant_id,
        payload=EmployeeCreateRequest(
            email="erin@acme-test.example",
            full_name="Erin Again",
            employee_code="EMP-E1",
            department_id=department_id,
        ),
    )
    assert recreated.email == "erin@acme-test.example"
    assert recreated.employee_code == "EMP-E1"

    # A second delete is 404, and the audit diff kept the original email.
    assert (
        await client.delete(f"/api/v1/auth/employees/{target.id}", headers=headers)
    ).status_code == 404
    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "employee_deleted"))
    ).scalar_one()
    assert audit.diff == {"email": "erin@acme-test.example"}


@pytest.mark.parametrize(
    ("method", "suffix"), [("POST", "/disable"), ("POST", "/enable"), ("DELETE", "")]
)
async def test_employee_removal_endpoints_require_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    user_without_permissions: User,
    issue_token: Callable[[User], str],
    method: str,
    suffix: str,
) -> None:
    target = await _make_employee(db_session, tenant, email="fay@acme-test.example")
    response = await client.request(
        method,
        f"/api/v1/auth/employees/{target.id}{suffix}",
        headers={"Authorization": f"Bearer {issue_token(user_without_permissions)}"},
    )
    assert response.status_code == 403
    await db_session.refresh(target)
    assert target.is_active is True and target.deleted_at is None


@pytest.mark.parametrize(
    ("method", "suffix"), [("POST", "/disable"), ("POST", "/enable"), ("DELETE", "")]
)
async def test_employee_removal_unknown_id_not_found(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], method: str, suffix: str
) -> None:
    response = await client.request(
        method,
        f"/api/v1/auth/employees/{uuid.uuid4()}{suffix}",
        headers={"Authorization": f"Bearer {issue_token(user)}"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(("method", "suffix"), [("POST", "/disable"), ("DELETE", "")])
async def test_admin_cannot_disable_or_delete_self(
    client: AsyncClient, user: User, issue_token: Callable[[User], str], method: str, suffix: str
) -> None:
    response = await client.request(
        method,
        f"/api/v1/auth/employees/{user.id}{suffix}",
        headers={"Authorization": f"Bearer {issue_token(user)}"},
    )
    assert response.status_code == 409


async def test_last_active_admin_cannot_be_disabled_or_deleted(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    issue_token: Callable[[User], str],
) -> None:
    # A caller who may manage employees but is not themselves an Admin.
    manage_permission = (
        await db_session.execute(select(Permission).where(Permission.code == "employees:manage"))
    ).scalar_one()
    manager_role = RoleFactory.build(
        id=uuid.uuid4(), name="employee-manager", permissions=[manage_permission]
    )
    manager = UserFactory.build(
        id=uuid.uuid4(),
        email="manager@acme-test.example",
        hashed_password=hash_password("correct-password"),
        branch_roles=[UserBranchRole(id=uuid.uuid4(), role=manager_role, branch_id=None)],
    )
    db_session.add_all([manager_role, manager])
    await db_session.flush()
    db_session.add(TenantUserIndex(email=manager.email, tenant_id=tenant.id, user_id=manager.id))
    await db_session.commit()
    headers = {"Authorization": f"Bearer {issue_token(manager)}"}

    assert (
        await client.post(f"/api/v1/auth/employees/{user.id}/disable", headers=headers)
    ).status_code == 409
    assert (
        await client.delete(f"/api/v1/auth/employees/{user.id}", headers=headers)
    ).status_code == 409
    await db_session.refresh(user)
    assert user.is_active is True and user.deleted_at is None

    # With another active admin present, removing one is allowed.
    await db_session.refresh(tenant)
    await _make_employee(db_session, tenant, email="second-admin@acme-test.example", admin=True)
    assert (
        await client.post(f"/api/v1/auth/employees/{user.id}/disable", headers=headers)
    ).status_code == 200


async def test_employee_removal_tenant_schema_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    make_tenant_schema,
    open_tenant_session,
) -> None:
    target = await _make_employee(db_session, tenant, email="gus@acme-test.example")
    other_schema = "tenant_other_employee_removal_test"
    await make_tenant_schema(other_schema)
    async with open_tenant_session(other_schema) as other_session:
        other_user = UserFactory.build(
            id=uuid.uuid4(),
            email="gus-other@acme-test.example",
            hashed_password="x",
            is_active=True,
            disabled_by_admin=False,
        )
        other_session.add(other_user)
        await other_session.commit()

    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    assert (
        await client.post(f"/api/v1/auth/employees/{target.id}/disable", headers=headers)
    ).status_code == 200
    # An id that exists only in the other tenant's schema is unknown here.
    assert (
        await client.delete(f"/api/v1/auth/employees/{other_user.id}", headers=headers)
    ).status_code == 404
    async with open_tenant_session(other_schema) as other_session:
        refreshed = await UserRepository(other_session).get_by_id(other_user.id)
        assert refreshed is not None and refreshed.is_active is True


async def test_sync_keeps_admin_disabled_employee_disabled(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User
) -> None:
    target = await _make_employee(
        db_session, tenant, email="hal@acme-test.example", employee_code="EMP-H1"
    )
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    await client.post(f"/api/v1/auth/employees/{target.id}/disable", headers=headers)

    sync = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "hal@acme-test.example",
                    "fullName": "Hal Renamed",
                    "employeeCode": "EMP-H1",
                }
            ]
        },
        headers=headers,
    )
    assert sync.status_code == 200
    await db_session.refresh(target)
    assert target.full_name == "Hal Renamed"
    assert target.is_active is False and target.disabled_by_admin is True


async def test_sync_reactivates_employee_it_deactivated_itself(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User
) -> None:
    keep = {"email": "ivy@acme-test.example", "fullName": "Ivy", "employeeCode": "EMP-I1"}
    drop = {"email": "jon@acme-test.example", "fullName": "Jon", "employeeCode": "EMP-J1"}
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    await client.post(
        "/api/v1/auth/employees/sync", json={"employees": [keep, drop]}, headers=headers
    )
    await client.post("/api/v1/auth/employees/sync", json={"employees": [keep]}, headers=headers)
    jon = await UserRepository(db_session).get_by_email("jon@acme-test.example")
    assert jon is not None
    await db_session.refresh(jon)
    assert jon.is_active is False

    await client.post(
        "/api/v1/auth/employees/sync", json={"employees": [keep, drop]}, headers=headers
    )
    await db_session.refresh(jon)
    assert jon.is_active is True


async def test_sync_treats_deleted_employee_as_new(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User
) -> None:
    target = await _make_employee(
        db_session, tenant, email="kim@acme-test.example", employee_code="EMP-K1"
    )
    headers = {"Authorization": f"Bearer {await _login(client, user.email)}"}
    await client.delete(f"/api/v1/auth/employees/{target.id}", headers=headers)

    sync = await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {"email": "kim@acme-test.example", "fullName": "Kim", "employeeCode": "EMP-K1"}
            ]
        },
        headers=headers,
    )
    assert sync.status_code == 200
    assert sync.json()["data"]["created"] == ["kim@acme-test.example"]


# --- all-branch employees in branch-scoped listings -------------------------


async def test_list_employees_branch_scope_is_branch_members_plus_all_branch(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant, user: User, branch: Branch
) -> None:
    """Branch A's view = A's own people + every all-branch employee; an
    employee tied only to branch B is excluded, and the all-branch employee
    shows under both A and B.
    """
    branch_id = branch.id  # captured before commits expire the fixture instance
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Branch B", code="BR-B")
    other_branch_id = other_branch.id
    db_session.add(other_branch)
    await db_session.commit()
    a_only = await _make_role_holder_no_department(db_session, tenant, "host", branch_id)
    b_only = await _make_role_holder_no_department(db_session, tenant, "greeter", other_branch_id)
    a_only_email, b_only_email = a_only.email, b_only.email
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "allbranch@acme-test.example",
                    "fullName": "All Branch Employee",
                    "employeeCode": "EMP-AB1",
                }
            ]
        },
        headers=headers,
    )

    async def emails_for(branch_id: uuid.UUID) -> set[str]:
        response = await client.get(
            "/api/v1/auth/employees",
            params={"pageSize": 100},
            headers={**headers, "X-Branch-ID": str(branch_id)},
        )
        assert response.status_code == 200
        return {e["email"] for e in response.json()["data"]}

    in_a = await emails_for(branch_id)
    in_b = await emails_for(other_branch_id)
    assert "allbranch@acme-test.example" in in_a
    assert "allbranch@acme-test.example" in in_b
    assert a_only_email in in_a and b_only_email not in in_a
    assert b_only_email in in_b and a_only_email not in in_b


async def test_list_employees_multi_role_employee_listed_once_and_matches_role_filter(
    client: AsyncClient, db_session: AsyncSession, user: User, branch: Branch
) -> None:
    """One role at the branch, another company-wide, plus a second branch:
    still exactly one row, one `total`, and the `role` filter finds them.
    """
    branch_id = branch.id
    other_branch = BranchFactory.build(id=uuid.uuid4(), name="Branch C", code="BR-C")
    host_role = RoleFactory.build(id=uuid.uuid4(), name="MultiHost")
    guard_role = RoleFactory.build(id=uuid.uuid4(), name="MultiGuard")
    holder = UserFactory.build(
        id=uuid.uuid4(),
        email="multi@acme-test.example",
        full_name="Multi Role",
        branch_roles=[
            UserBranchRole(id=uuid.uuid4(), role=host_role, branch_id=branch_id),
            UserBranchRole(id=uuid.uuid4(), role=guard_role, branch_id=None),
            UserBranchRole(id=uuid.uuid4(), role=host_role, branch_id=other_branch.id),
        ],
    )
    db_session.add_all([other_branch, host_role, guard_role])
    await db_session.flush()
    db_session.add(holder)
    await db_session.commit()
    token = await _login(client, user.email)

    for params in ({}, {"role": "MultiHost"}, {"role": "MultiGuard"}):
        response = await client.get(
            "/api/v1/auth/employees",
            params={**params, "pageSize": 100},
            headers={"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch_id)},
        )
        body = response.json()
        rows = [e for e in body["data"] if e["email"] == "multi@acme-test.example"]
        assert len(rows) == 1
        if params:
            assert body["pagination"]["total"] == 1


async def test_all_branch_employee_can_be_disabled_and_deleted_from_branch_view(
    client: AsyncClient, user: User, branch: Branch
) -> None:
    token = await _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}", "X-Branch-ID": str(branch.id)}
    await client.post(
        "/api/v1/auth/employees/sync",
        json={
            "employees": [
                {
                    "email": "ab-manage@acme-test.example",
                    "fullName": "AB Manage",
                    "employeeCode": "EMP-AB2",
                }
            ]
        },
        headers=headers,
    )
    listing = await client.get("/api/v1/auth/employees", params={"pageSize": 100}, headers=headers)
    target = next(e for e in listing.json()["data"] if e["email"] == "ab-manage@acme-test.example")

    disabled = await client.post(f"/api/v1/auth/employees/{target['id']}/disable", headers=headers)
    assert disabled.status_code == 200
    enabled = await client.post(f"/api/v1/auth/employees/{target['id']}/enable", headers=headers)
    assert enabled.status_code == 200
    deleted = await client.delete(f"/api/v1/auth/employees/{target['id']}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get("/api/v1/auth/employees", params={"pageSize": 100}, headers=headers)
    assert target["id"] not in {e["id"] for e in after.json()["data"]}


# --- Employee directory free-text search ----------------------------------


async def _search_emails(client: AsyncClient, query: str) -> tuple[set[str], int]:
    response = await client.get("/api/v1/auth/employees", params=query_params(query))
    assert response.status_code == 200
    body = response.json()
    return {row["email"] for row in body["data"]}, body["pagination"]["total"]


def query_params(search: str, **extra: str) -> dict[str, str]:
    return {"search": search, **extra}


async def test_list_employees_search_matches_name_email_and_code(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    await _make_employee(
        db_session, tenant, email="searchdina@acme-test.example", employee_code="SRCH-0012"
    )
    await _make_employee(
        db_session, tenant, email="plain@acme-test.example", employee_code="SRCH-0034"
    )
    await _make_employee(db_session, tenant, email="other@acme-test.example", employee_code="ZZZ-1")

    by_name, total = await _search_emails(client, "SEARCHDINA")
    assert by_name == {"searchdina@acme-test.example"}
    assert total == 1

    by_email, _ = await _search_emails(client, "plain@acme")
    assert by_email == {"plain@acme-test.example"}

    by_code, total = await _search_emails(client, "srch-00")
    assert by_code == {"searchdina@acme-test.example", "plain@acme-test.example"}
    assert total == 2


async def test_list_employees_search_combines_with_status_filter(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    active = await _make_employee(db_session, tenant, email="combo-a@acme-test.example")
    inactive = await _make_employee(db_session, tenant, email="combo-b@acme-test.example")
    inactive.is_active = False
    await db_session.commit()

    response = await client.get(
        "/api/v1/auth/employees", params={"search": "combo-", "status": "active"}
    )
    assert response.status_code == 200
    assert {r["email"] for r in response.json()["data"]} == {active.email}
    assert response.json()["pagination"]["total"] == 1


async def test_list_employees_search_treats_wildcards_literally(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    await _make_employee(db_session, tenant, email="wild@acme-test.example", employee_code="W%1")
    await _make_employee(db_session, tenant, email="nowild@acme-test.example", employee_code="W91")

    emails, total = await _search_emails(client, "W%")
    assert emails == {"wild@acme-test.example"}
    assert total == 1

    emails, _ = await _search_emails(client, "W_1")
    assert emails == set()


async def test_list_employees_blank_search_is_ignored(
    client: AsyncClient, db_session: AsyncSession, tenant: Tenant
) -> None:
    await _make_employee(db_session, tenant, email="blank@acme-test.example")
    baseline = await client.get("/api/v1/auth/employees")
    blank = await client.get("/api/v1/auth/employees", params={"search": "   "})
    assert blank.status_code == 200
    assert blank.json()["pagination"]["total"] == baseline.json()["pagination"]["total"]


async def test_list_employees_search_over_255_chars_rejected(
    client: AsyncClient, tenant: Tenant
) -> None:
    response = await client.get("/api/v1/auth/employees", params={"search": "a" * 256})
    assert response.status_code in (400, 422)
