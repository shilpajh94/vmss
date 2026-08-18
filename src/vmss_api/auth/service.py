import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import Role, User, UserBranchRole
from vmss_api.auth.repository import RoleRepository, UserRepository
from vmss_api.auth.schemas import (
    EmployeeSortableField,
    EmployeeSyncItem,
    EmployeeSyncResult,
    TokenResponse,
    UserCreateRequest,
)
from vmss_api.core.database import tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.schemas import SortOrder
from vmss_api.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from vmss_api.org_structure.repository import BranchRepository, DepartmentRepository
from vmss_api.platform.repository import TenantUserIndexRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository


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
        logger.warning("login_failed", email=email, reason="no_tenant_for_email")
        raise invalid_credentials

    tenant = await TenantRepository(db).get(index_entry.tenant_id)
    if tenant is None or not tenant.is_active:
        logger.warning("login_failed", email=email, reason="tenant_not_found_or_inactive")
        raise invalid_credentials

    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        user = await UserRepository(tenant_db).get_by_id(index_entry.user_id)

    if user is None or not user.is_active:
        logger.warning("login_failed", email=email, reason="user_not_found_or_inactive")
        raise invalid_credentials
    if not verify_password(password, user.hashed_password):
        logger.warning("login_failed", email=email, reason="invalid_password", user_id=str(user.id))
        raise invalid_credentials
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
    await tenant_db.flush()
    await TenantUserIndexRepository(tenant_db).create(
        email=email, tenant_id=tenant_id, user_id=user.id
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
    await tenant_db.commit()
    logger.info(
        "branch_role_assigned",
        target_user_id=str(user_id),
        role_id=str(role_id),
        branch_id=str(branch_id) if branch_id else None,
    )
    return assignment


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

    for item in items:
        existing = existing_by_email.get(item.email)
        if existing is None:
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
            )
            created.append(item.email)
        else:
            existing.full_name = item.full_name
            existing.employee_code = item.employee_code
            existing.designation = item.designation
            existing.phone_number = item.phone_number
            existing.department_id = item.department_id
            existing.is_active = True
            updated.append(item.email)

    await tenant_db.flush()
    deactivated = await user_repo.deactivate_employees_not_in(incoming_codes)

    try:
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


async def list_employees(
    tenant_db: AsyncSession,
    *,
    authorized_branch_id: uuid.UUID,
    department_id: uuid.UUID | None,
    page: int,
    page_size: int,
    sort_by: EmployeeSortableField,
    sort_order: SortOrder,
) -> tuple[list[User], int]:
    return await UserRepository(tenant_db).list_employees_page(
        authorized_branch_id=authorized_branch_id,
        department_id=department_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
