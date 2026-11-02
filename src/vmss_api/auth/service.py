from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from vmss_api.auth.models import Permission, Role, User, UserBranchRole
from vmss_api.auth.rbac_catalog import STANDARD_ROLE_NAMES, seed_default_roles
from vmss_api.auth.repository import PermissionRepository, RoleRepository, UserRepository
from vmss_api.auth.schemas import (
    EmployeeCreateRequest,
    EmployeeSortableField,
    EmployeeStatus,
    EmployeeSyncItem,
    EmployeeSyncResult,
    PermissionSortableField,
    RoleCreateRequest,
    RoleSortableField,
    RoleUpdateRequest,
    TokenResponse,
    UserCreateRequest,
)
from vmss_api.core.config import settings
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.masking import mask_identifier
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from vmss_api.core.storage import save as storage_save
from vmss_api.core.storage import validate_image_only
from vmss_api.org_structure.repository import BranchRepository, DepartmentRepository
from vmss_api.platform.repository import TenantUserIndexRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def has_admin_role(user: User) -> bool:
    """Whether `user` holds the Admin role via any (company-wide or
    branch-scoped) `UserBranchRole` grant. Used to gate which login method
    an account may use — `POST /auth/login` (this module) requires it,
    `sso-authentication`'s callback requires its absence — see
    `openspec/changes/separate-admin-staff-login/design.md`.
    """
    return any(assignment.role.name == "admin" for assignment in user.branch_roles)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[User, Tenant]:
    """Login's two-hop lookup under schema-per-tenant: the global
    `tenant_user_index` says *which* tenant this email belongs to; only then
    can the actual `User` row (in that tenant's own schema) be loaded and
    the password checked. `db` is a plain, global-schema session (see
    `core/tenancy.py` for why a tenant-bound session isn't available yet at
    this point in the request). Returns the full `Tenant`, not just its id,
    so the router can also read `schema_name` for the login audit-log entry
    (`auth/audit.py`).
    """
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )

    index_entry = await TenantUserIndexRepository(db).get_by_email(email)
    if index_entry is None:
        logger.warning("login_failed", email=mask_identifier(email), reason="no_tenant_for_email")
        raise invalid_credentials

    tenant = await TenantRepository(db).get(index_entry.tenant_id)
    if tenant is None or not tenant.is_active:
        logger.warning(
            "login_failed", email=mask_identifier(email), reason="tenant_not_found_or_inactive"
        )
        raise invalid_credentials

    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        user = await UserRepository(tenant_db).get_by_id(index_entry.user_id)

    if user is None or not user.is_active:
        logger.warning(
            "login_failed", email=mask_identifier(email), reason="user_not_found_or_inactive"
        )
        raise invalid_credentials
    if not verify_password(password, user.hashed_password):
        logger.warning(
            "login_failed",
            email=mask_identifier(email),
            reason="invalid_password",
            user_id=str(user.id),
        )
        raise invalid_credentials
    if not has_admin_role(user):
        logger.warning(
            "login_rejected_non_admin", email=mask_identifier(email), user_id=str(user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account must sign in via your organization's SSO login",
        )
    return user, tenant


def issue_tokens(user: User, tenant_id: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, tenant_id),
        refresh_token=create_refresh_token(user.id, tenant_id),
    )


async def create_user(
    tenant_db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    hashed_password: str,
    full_name: str,
    role_assignments: list[tuple[Role, uuid.UUID | None]] | None = None,
    employee_code: str | None = None,
    designation: str | None = None,
    phone_number: str | None = None,
    department_id: uuid.UUID | None = None,
    flush: bool = True,
) -> User:
    """Creates a `User` in the tenant schema `tenant_db` is bound to, grants
    it any `(role, branch_id)` pairs in `role_assignments` (`branch_id=None`
    meaning company-wide — see `auth/models.py::UserBranchRole`), and
    registers it in the global `tenant_user_index` in the same transaction —
    that index has to stay consistent with every tenant's `users` table for
    login's first hop (`authenticate_user` above) to work. Callers commit.

    The `employee_*`/`department_id` kwargs are only populated by
    `sync_employee_directory` below — a company-wide Admin/Security account
    created via `register_user` has none of them.

    `branch_roles` is populated via the constructor, not added separately
    after flush: `User.branch_roles` is `lazy="selectin"`, but that only
    covers eager-loading on a *query* — an attribute never populated at all
    (construction or query) still triggers an implicit lazy load on first
    access, which raises `MissingGreenlet` under async SQLAlchemy outside a
    query context. See query-performance.md §1.
    """
    branch_roles = [
        UserBranchRole(id=uuid.uuid4(), role_id=role.id, branch_id=branch_id)
        for role, branch_id in role_assignments or []
    ]
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        branch_roles=branch_roles,
        employee_code=employee_code,
        designation=designation,
        phone_number=phone_number,
        department_id=department_id,
    )
    tenant_db.add(user)
    if flush:
        await tenant_db.flush()
    # `flush=False` lets a batch caller (`sync_employee_directory`) flush
    # every new user and index row once: ids are client-assigned, and the
    # index row has no foreign key onto the tenant's `users` table.
    await TenantUserIndexRepository(tenant_db).create(
        email=email, tenant_id=tenant_id, user_id=user.id, flush=flush
    )
    return user


async def register_user(
    tenant_db: AsyncSession, *, tenant_id: uuid.UUID, payload: UserCreateRequest
) -> User:
    """Endpoint-facing wrapper around `create_user` — validates the email
    isn't already taken (in this tenant) and hashes the password. Grants no
    role; use `assign_branch_role` afterward to give the new user access.
    """
    if await UserRepository(tenant_db).get_by_email(payload.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await create_user(
        tenant_db,
        tenant_id=tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    await tenant_db.commit()
    return user


async def assign_branch_role(
    tenant_db: AsyncSession, *, user_id: uuid.UUID, role_id: uuid.UUID, branch_id: uuid.UUID | None
) -> UserBranchRole:
    """Grants `role_id` to `user_id`, scoped to `branch_id` — or every branch
    in the company when `branch_id` is `None`. Validates the user, role, and
    (when given) branch all exist in this tenant before writing the grant.
    """
    user = await UserRepository(tenant_db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    role = await RoleRepository(tenant_db).get(role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.name == "visitor":
        # Visitors never authenticate through this JWT/RBAC system — see
        # rbac_catalog.py's "visitor" entry — so granting it to a `User` row
        # would be inert (zero permissions) and semantically wrong.
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Visitor role cannot be assigned to a user"
        )
    if branch_id is not None and await BranchRepository(tenant_db).get(branch_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")

    assignment = UserBranchRole(
        id=uuid.uuid4(), user_id=user_id, role_id=role_id, branch_id=branch_id
    )
    assignment.role = role
    tenant_db.add(assignment)
    try:
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="User already holds this role at this branch"
        ) from exc
    logger.info(
        "branch_role_assigned",
        target_user_id=str(user_id),
        role_id=str(role_id),
        branch_id=str(branch_id) if branch_id else None,
    )
    return assignment


async def revoke_branch_role(
    tenant_db: AsyncSession, *, user_id: uuid.UUID, assignment_id: uuid.UUID
) -> None:
    repo = UserRepository(tenant_db)
    assignment = await repo.get_branch_role_assignment(user_id, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch role assignment not found")
    await repo.delete_branch_role_assignment(assignment)
    await tenant_db.commit()
    logger.info(
        "branch_role_revoked", target_user_id=str(user_id), assignment_id=str(assignment_id)
    )


async def list_permissions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    sort_by: PermissionSortableField,
    sort_order: SortOrder,
) -> tuple[list[Permission], int]:
    """The tenant-independent permission catalog (global schema) — lets a
    role-creation/update form populate its permission-code choices instead
    of guessing. See `Requirement: Role Permission Codes Must Exist in the
    Catalog` (openspec/specs/auth/spec.md).
    """
    return await PermissionRepository(db).list_page(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


async def _resolve_permission_codes(repo: RoleRepository, codes: list[str]) -> list[Permission]:
    if not codes:
        return []
    permissions = await repo.get_existing_permissions(codes)
    missing = set(codes) - {p.code for p in permissions}
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown permission code(s): {', '.join(sorted(missing))}",
        )
    return permissions


async def create_role(tenant_db: AsyncSession, payload: RoleCreateRequest) -> Role:
    repo = RoleRepository(tenant_db)
    if await repo.get_by_name_case_insensitive(payload.name) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Role name already exists")
    permissions = await _resolve_permission_codes(repo, payload.permission_codes)
    role = Role(
        id=uuid.uuid4(), name=payload.name, description=payload.description, permissions=permissions
    )
    tenant_db.add(role)
    try:
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Role name already exists") from exc
    await tenant_db.refresh(role)
    return role


async def list_roles(
    tenant_db: AsyncSession,
    *,
    page: int,
    page_size: int,
    sort_by: RoleSortableField,
    sort_order: SortOrder,
) -> tuple[list[Role], int]:
    return await RoleRepository(tenant_db).list_page(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


async def get_role(tenant_db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await RoleRepository(tenant_db).get(role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


async def update_role(
    tenant_db: AsyncSession, role_id: uuid.UUID, payload: RoleUpdateRequest
) -> Role:
    """Standard roles (`rbac_catalog.STANDARD_ROLE_NAMES`) may have their
    description or permission set updated, but never renamed — see
    `openspec/changes/add-role-management-and-org-field-gaps/design.md`
    Decision 1. Permission-set updates are full-replace, not a merge — see
    the same design doc's Decision 2.
    """
    repo = RoleRepository(tenant_db)
    role = await get_role(tenant_db, role_id)
    changes = payload.model_dump(exclude_unset=True)

    new_name = changes.get("name")
    if new_name is not None and new_name != role.name:
        if role.name in STANDARD_ROLE_NAMES:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Standard roles cannot be renamed")
        if await repo.get_by_name_case_insensitive(new_name) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Role name already exists")
        role.name = new_name

    if "description" in changes:
        role.description = changes["description"]

    new_codes = changes.get("permission_codes")
    if new_codes is not None:
        role.permissions = await _resolve_permission_codes(repo, new_codes)

    try:
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Role name already exists") from exc
    await tenant_db.refresh(role)
    return role


async def delete_role(tenant_db: AsyncSession, role_id: uuid.UUID) -> None:
    repo = RoleRepository(tenant_db)
    role = await get_role(tenant_db, role_id)
    if role.name in STANDARD_ROLE_NAMES:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Standard roles cannot be deleted")
    if await repo.has_active_grants(role.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Role has active branch-role assignments"
        )
    await repo.soft_delete(role)
    await tenant_db.commit()


async def verify_role_name(tenant_db: AsyncSession, name: str) -> bool:
    """Returns whether `name` is available (case-insensitive, among
    non-deleted roles) for the role-creation/rename "verify" pre-check.
    """
    existing = await RoleRepository(tenant_db).get_by_name_case_insensitive(name)
    return existing is None


# Visitor is intentionally always granted nothing (`rbac_catalog.py`'s own
# comment on `ROLE_PERMISSIONS["visitor"]`) — excluded here since resyncing
# it can never do anything (`add-invitation-approval-flow-and-role-resync/
# design.md`'s Non-Goals).
_RESYNCABLE_ROLE_NAMES = STANDARD_ROLE_NAMES - {"visitor"}


async def resync_role_permissions(tenant_db: AsyncSession) -> dict[str, list[str]]:
    """Backfills any catalog-defined permission a standard role is
    currently missing, by re-running `seed_default_roles`'s union-merge
    against an already-provisioned tenant instead of only at provisioning
    time (design.md Decision 5) — fixes a tenant whose roles predate a
    permission being added to the catalog (`rbac_catalog.py`'s own
    docstring on this exact failure mode). Additive only: never removes a
    permission, including one a role holds outside its catalog default.
    Returns each resynced role's newly granted permission codes (empty
    list if it already had everything the catalog currently grants it).
    """
    repo = RoleRepository(tenant_db)
    roles_by_name: dict[str, Role] = {}
    before_codes: dict[str, set[str]] = {}
    for role in await repo.get_by_names(_RESYNCABLE_ROLE_NAMES):
        roles_by_name[role.name] = role
        before_codes[role.name] = {p.code for p in role.permissions}

    await seed_default_roles(tenant_db)
    await tenant_db.commit()

    return {
        name: sorted({p.code for p in role.permissions} - before_codes[name])
        for name, role in roles_by_name.items()
    }


async def sync_employee_directory(
    tenant_db: AsyncSession, *, tenant_id: uuid.UUID, items: list[EmployeeSyncItem]
) -> EmployeeSyncResult:
    """Reconciles the employee directory against `items`, treated as the
    full, authoritative batch (not a partial delta): every existing employee
    (`User.employee_code` set) whose code isn't in this batch is deactivated,
    matching testing-standards.md/api-conventions.md's "manual bulk sync"
    scope decided for this feature — no external HRMS/LDAP connector.

    New employees are created with an unusable random password (they can't
    log in until an Admin issues real credentials through a future
    password-reset flow) — sync only manages directory data, never
    credentials. Validates every `department_id` referenced before writing
    anything, so a bad row aborts the whole batch instead of partially
    applying it.

    Every lookup below is batched (one `IN (...)` query for the whole batch,
    one bulk `UPDATE` for deactivation) rather than looped per item — a batch
    of up to 1000 rows (`EmployeeSyncRequest.employees`' `max_length`) looping
    one query per row is exactly the N+1 pattern query-performance.md §2/§3
    forbid.
    """
    department_ids = {item.department_id for item in items if item.department_id is not None}
    if department_ids:
        existing_department_ids = await DepartmentRepository(tenant_db).get_existing_ids(
            department_ids
        )
        missing = department_ids - existing_department_ids
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Department(s) not found: {', '.join(str(d) for d in sorted(missing))}",
            )

    user_repo = UserRepository(tenant_db)
    existing_users = await user_repo.get_by_emails([item.email for item in items])
    existing_by_email = {u.email: u for u in existing_users}
    created: list[str] = []
    updated: list[str] = []
    incoming_codes = [item.employee_code for item in items]

    try:
        for item in items:
            existing = existing_by_email.get(item.email)
            if existing is None:
                # Not flushed per row: the single flush after the loop writes
                # every new user and index row, and a duplicate
                # employee_code/email still surfaces there as the same
                # IntegrityError -> 409 the per-row flush used to raise.
                await create_user(
                    tenant_db,
                    tenant_id=tenant_id,
                    email=item.email,
                    hashed_password=hash_password(secrets.token_urlsafe(32)),
                    full_name=item.full_name,
                    employee_code=item.employee_code,
                    designation=item.designation,
                    phone_number=item.phone_number,
                    department_id=item.department_id,
                    flush=False,
                )
                created.append(item.email)
            else:
                existing.full_name = item.full_name
                existing.employee_code = item.employee_code
                existing.designation = item.designation
                existing.phone_number = item.phone_number
                existing.department_id = item.department_id
                if not existing.disabled_by_admin:
                    existing.is_active = True
                updated.append(item.email)

        await tenant_db.flush()
        deactivated = await user_repo.deactivate_employees_not_in(incoming_codes)
        await tenant_db.commit()
    except IntegrityError as exc:
        await tenant_db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Duplicate employee code or email in batch"
        ) from exc

    logger.info(
        "employee_directory_synced",
        created_count=len(created),
        updated_count=len(updated),
        deactivated_count=len(deactivated),
    )
    return EmployeeSyncResult(created=created, updated=updated, deactivated=deactivated)


async def create_employee(
    tenant_db: AsyncSession, *, tenant_id: uuid.UUID, payload: EmployeeCreateRequest
) -> User:
    """Creates one employee directly, unlike `sync_employee_directory` this
    never touches any other existing employee's `is_active` status — see
    `Requirement: Single Employee Creation Without a Full Directory Sync` in
    openspec/specs/auth/spec.md. When `payload.password` is given it becomes
    the account's real password; otherwise an unusable random one is set,
    same as sync.
    """
    if await UserRepository(tenant_db).get_by_email(payload.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    existing_department_ids = await DepartmentRepository(tenant_db).get_existing_ids(
        {payload.department_id}
    )
    if payload.department_id not in existing_department_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Department not found")

    user = await create_user(
        tenant_db,
        tenant_id=tenant_id,
        email=payload.email,
        hashed_password=hash_password(payload.password or secrets.token_urlsafe(32)),
        full_name=payload.full_name,
        employee_code=payload.employee_code,
        designation=payload.designation,
        phone_number=payload.phone_number,
        department_id=payload.department_id,
    )
    await tenant_db.commit()
    return user


async def _get_employee_for_removal(
    tenant_db: AsyncSession, *, employee_id: uuid.UUID, actor_id: uuid.UUID
) -> User:
    """Shared guard for disable/delete: 404 on unknown, 409 when the actor
    targets themself or the target is the tenant's last active admin.
    """
    repo = UserRepository(tenant_db)
    employee = await repo.get_by_id(employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if employee.id == actor_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="You cannot disable or delete your own account"
        )
    if employee.is_active and has_admin_role(employee):
        active_admins = await repo.lock_active_admin_ids()
        if active_admins <= {employee.id}:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="At least one active admin must remain",
            )
    return employee


async def disable_employee(
    tenant_db: AsyncSession, *, employee_id: uuid.UUID, actor_id: uuid.UUID
) -> tuple[User, bool]:
    """Reversible disable: `is_active=False` plus `disabled_by_admin` so a
    later directory sync leaves it alone. Returns `(employee, changed)`;
    disabling an already-disabled employee is a no-op (`changed=False`), so
    the caller can skip the audit entry. Existing tokens stop working
    because `get_current_user` rejects inactive users on every request.
    """
    employee = await _get_employee_for_removal(
        tenant_db, employee_id=employee_id, actor_id=actor_id
    )
    if employee.disabled_by_admin and not employee.is_active:
        return employee, False
    employee.is_active = False
    employee.disabled_by_admin = True
    await tenant_db.commit()
    await tenant_db.refresh(employee)
    logger.info("employee_disabled", target_user_id=str(employee.id))
    return employee, True


async def enable_employee(tenant_db: AsyncSession, *, employee_id: uuid.UUID) -> tuple[User, bool]:
    employee = await UserRepository(tenant_db).get_by_id(employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if employee.is_active and not employee.disabled_by_admin:
        return employee, False
    employee.is_active = True
    employee.disabled_by_admin = False
    await tenant_db.commit()
    await tenant_db.refresh(employee)
    logger.info("employee_enabled", target_user_id=str(employee.id))
    return employee, True


async def delete_employee(
    tenant_db: AsyncSession, *, employee_id: uuid.UUID, actor_id: uuid.UUID
) -> str:
    """Soft-deletes an employee and frees their email/employee code. The
    global `tenant_user_index` row is removed in the same transaction as the
    tombstone (both share one connection), so login's first hop and the
    `users` table can't disagree. Returns the original email for the audit
    diff, since the row itself no longer holds it.
    """
    employee = await _get_employee_for_removal(
        tenant_db, employee_id=employee_id, actor_id=actor_id
    )
    original_email = employee.email
    await TenantUserIndexRepository(tenant_db).delete_by_email(original_email)
    await UserRepository(tenant_db).tombstone(employee)
    await tenant_db.commit()
    logger.info("employee_deleted", target_user_id=str(employee_id))
    return original_email


async def list_employees(
    tenant_db: AsyncSession,
    *,
    branch_scope: BranchScope,
    department_id: uuid.UUID | None,
    email: str | None,
    role: str | None,
    status: EmployeeStatus | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: EmployeeSortableField,
    sort_order: SortOrder,
) -> tuple[list[User], int]:
    return await UserRepository(tenant_db).list_employees_page(
        branch_scope=branch_scope,
        department_id=department_id,
        email=email,
        role=role,
        status=status,
        search=(search or "").strip() or None,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def list_employee_directory(
    tenant_db: AsyncSession,
    *,
    page: int,
    page_size: int,
    sort_by: EmployeeSortableField,
    sort_order: SortOrder,
) -> tuple[list[User], int]:
    """Backs the public host-directory listing
    (`router.py::list_employee_directory`) — every active employee holding
    the `host` role (a Reception/Security/Admin account is staff, not
    someone a visitor can be pre-registered against). Not branch/department
    scoped — see `UserRepository.list_hosts_page`.
    """
    return await UserRepository(tenant_db).list_hosts_page(
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )


async def upload_avatar(
    tenant_db: AsyncSession, *, tenant_id: uuid.UUID, user: User, content: bytes
) -> User:
    """Validates and stores a user's own profile picture, same content-
    sniffing/size approach as `invitations/service.py::_validate_photo`
    (image-only, no PDF) — see
    add-avatar-upload-and-verify-image-storage/design.md Decision 2.
    `avatar_url` stores the opaque storage key, resolved to a fetchable URL
    at response-construction time in `router.py`, mirroring how
    `invitations` resolves `photo_storage_key` -> `photo_url`. On a
    rejected upload, `user`'s existing avatar (if any) is left unchanged —
    validation runs before any write.
    """
    content_type = validate_image_only(
        content, max_size_bytes=settings.avatar_max_upload_size_bytes, field_label="avatar"
    )
    storage_key = await storage_save(tenant_id, "auth/avatars", content, content_type)
    user.avatar_url = storage_key
    await tenant_db.commit()
    await tenant_db.refresh(user)
    return user
