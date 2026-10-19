import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth import service
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import Role, User
from vmss_api.auth.rbac_catalog import STANDARD_ROLE_NAMES
from vmss_api.auth.schemas import (
    AvatarUploadOut,
    BranchRoleAssignRequest,
    BranchRoleOut,
    EmployeeCreateRequest,
    EmployeeDirectoryOut,
    EmployeeOut,
    EmployeeSortableField,
    EmployeeStatus,
    EmployeeSyncRequest,
    EmployeeSyncResult,
    LoginRequest,
    PermissionOut,
    PermissionSortableField,
    RoleCreateRequest,
    RoleOut,
    RolePermissionResyncEntryOut,
    RoleSortableField,
    RoleUpdateRequest,
    RoleVerifyResponse,
    TokenResponse,
    UserCreateRequest,
    UserOut,
)
from vmss_api.core.config import settings
from vmss_api.core.database import get_db
from vmss_api.core.deps import (
    get_current_user,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_permission,
    require_permission_anywhere,
)
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.core.storage import url_for as storage_url_for
from vmss_api.org_structure.deps import public_branch_scope, public_tenant_db
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Envelope[TokenResponse])
@limiter.limit("3/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Rate-limited (3/min per IP) — this is a public, unauthenticated endpoint.
    Tightened from 5/min now that SSO (API-19) makes this the break-glass
    path and the higher-value brute-force target once SSO is the default
    way in. See security-architecture.md §2.
    """
    user, tenant = await service.authenticate_user(db, payload.email, payload.password)
    tokens = service.issue_tokens(user, tenant.id)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="login",
        entity_type="User",
        entity_id=user.id,
    )
    return success_response(data=tokens)


@router.post("/logout", response_model=Envelope[None])
async def logout(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Records the logout audit event (docx acceptance checklist: "every
    SSO login, logout... shows up in the audit log") — this app issues
    stateless JWTs with no revocation list, so this does not invalidate the
    caller's still-valid access token; see
    `openspec/changes/add-sso-oidc-login/design.md`'s Non-Goals.
    """
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="logout",
        entity_type="User",
        entity_id=actor.id,
    )
    return success_response(data=None)


async def _resolve_avatar_url(storage_key: str | None) -> str | None:
    return await storage_url_for(storage_key) if storage_key is not None else None


async def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        avatar_url=await _resolve_avatar_url(user.avatar_url),
        branch_roles=[
            BranchRoleOut(id=a.id, role_name=a.role.name, branch_id=a.branch_id)
            for a in user.branch_roles
        ],
    )


@router.get("/me", response_model=Envelope[UserOut])
async def get_my_profile(user: Annotated[User, Depends(get_current_user)]) -> JSONResponse:
    return success_response(data=await _to_user_out(user))


@router.post("/me/avatar", response_model=Envelope[AvatarUploadOut])
async def upload_my_avatar(
    file: Annotated[UploadFile, File(...)],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Bounded read (`file-upload-handling.md` §1,
    add-avatar-upload-and-verify-image-storage/design.md Decision 3) —
    rejects an oversized file before its full content is buffered into
    memory, matching `invitations`' upload endpoints.
    """
    content = await file.read(settings.avatar_max_upload_size_bytes + 1)
    updated = await service.upload_avatar(
        tenant_db, tenant_id=tenant.id, user=actor, content=content
    )
    return success_response(
        data=AvatarUploadOut(avatar_url=await _resolve_avatar_url(updated.avatar_url))
    )


@router.post(
    "/users",
    response_model=Envelope[UserOut],
    dependencies=[Depends(require_permission("users:manage"))],
    status_code=201,
)
async def create_user(
    payload: UserCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    new_user = await service.register_user(tenant_db, tenant_id=tenant.id, payload=payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="user_created",
        entity_type="User",
        entity_id=new_user.id,
    )
    return success_response(data=await _to_user_out(new_user), status_code=201)


@router.post(
    "/users/{user_id}/branch-roles",
    response_model=Envelope[BranchRoleOut],
    dependencies=[Depends(require_permission("users:manage"))],
    status_code=201,
)
async def assign_branch_role(
    user_id: uuid.UUID,
    payload: BranchRoleAssignRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    assignment = await service.assign_branch_role(
        tenant_db, user_id=user_id, role_id=payload.role_id, branch_id=payload.branch_id
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="branch_role_assigned",
        entity_type="User",
        entity_id=user_id,
        diff={"role_id": str(payload.role_id), "branch_id": str(payload.branch_id or "")},
    )
    return success_response(
        data=BranchRoleOut(
            id=assignment.id, role_name=assignment.role.name, branch_id=assignment.branch_id
        ),
        status_code=201,
    )


@router.delete(
    "/users/{user_id}/branch-roles/{assignment_id}",
    dependencies=[Depends(require_permission("users:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_branch_role(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.revoke_branch_role(tenant_db, user_id=user_id, assignment_id=assignment_id)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="branch_role_revoked",
        entity_type="User",
        entity_id=user_id,
        diff={"assignment_id": str(assignment_id)},
    )


async def _to_employee_out(user: User) -> EmployeeOut:
    return EmployeeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        employee_code=user.employee_code,
        phone_number=user.phone_number,
        designation=user.designation,
        department_id=user.department_id,
        is_active=user.is_active,
        avatar_url=await _resolve_avatar_url(user.avatar_url),
        branch_roles=[
            BranchRoleOut(id=a.id, role_name=a.role.name, branch_id=a.branch_id)
            for a in user.branch_roles
        ],
    )


@router.post(
    "/employees/sync",
    response_model=Envelope[EmployeeSyncResult],
    dependencies=[Depends(require_permission("employees:manage"))],
)
async def sync_employee_directory(
    payload: EmployeeSyncRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Company-wide only, not branch-scoped: a directory sync batch spans
    every employee across every department/branch in one call by design —
    see `auth/service.py::sync_employee_directory`.
    """
    result = await service.sync_employee_directory(
        tenant_db, tenant_id=tenant.id, items=payload.employees
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="employee_directory_synced",
        entity_type="User",
        entity_id=None,
        diff={
            "created": len(result.created),
            "updated": len(result.updated),
            "deactivated": len(result.deactivated),
        },
    )
    return success_response(data=result)


@router.post(
    "/employees",
    response_model=Envelope[EmployeeOut],
    dependencies=[Depends(require_permission("employees:manage"))],
    status_code=201,
)
async def create_employee(
    payload: EmployeeCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Creates one employee, immediately visible in `GET /employees` — unlike
    `sync_employee_directory` above, this never deactivates any other
    employee. See `auth/service.py::create_employee`.
    """
    new_employee = await service.create_employee(tenant_db, tenant_id=tenant.id, payload=payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="employee_created",
        entity_type="User",
        entity_id=new_employee.id,
    )
    return success_response(data=await _to_employee_out(new_employee), status_code=201)


@router.get(
    "/employees",
    response_model=PaginatedEnvelope[EmployeeOut],
)
@limiter.limit("60/minute")
async def list_employees(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    department_id: Annotated[uuid.UUID | None, Query(alias="departmentId")] = None,
    email: Annotated[EmailStr | None, Query()] = None,
    role: Annotated[str | None, Query(max_length=100)] = None,
    employee_status: Annotated[EmployeeStatus | None, Query(alias="status")] = None,
    sort_by: Annotated[EmployeeSortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """No bearer token or permission required: tenant resolves from a
    presented access token when valid, otherwise `settings.default_tenant_slug`
    (`org_structure/deps.py::public_tenant_db`/`public_branch_scope`, the
    same mechanism already used by the public org-structure listing
    endpoints). Rate-limited by client IP (60/minute), consistent with
    every other unauthenticated endpoint (`security-architecture.md` §2).
    `X-Branch-ID` is optional: scopes to that one branch when supplied,
    otherwise every branch in the resolved tenant. Employees are matched to
    a branch via `department_id -> Department.branch_id`, OR via their own
    `UserBranchRole.branch_id` (a specific-branch or company-wide/"All
    Branch" role grant) — so a delegate-candidate lookup
    (`?role=host&X-Branch-ID=...`) still surfaces a host whose role grant
    is company-wide even if they have no department set at that branch. An
    employee with neither a matching department nor a matching/company-wide
    role grant is not visible in a branch-scoped call — see
    `auth/repository.py::UserRepository.list_employees_page`.
    """
    page, page_size = pagination
    employees, total = await service.list_employees(
        tenant_db,
        branch_scope=branch_scope,
        department_id=department_id,
        email=email,
        role=role,
        status=employee_status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    employee_outs = [await _to_employee_out(e) for e in employees]
    return paginated_response(data=employee_outs, page=page, page_size=page_size, total=total)


async def _to_employee_directory_out(user: User) -> EmployeeDirectoryOut:
    return EmployeeDirectoryOut(
        id=user.id,
        full_name=user.full_name,
        designation=user.designation,
        department_id=user.department_id,
        avatar_url=await _resolve_avatar_url(user.avatar_url),
    )


@router.get(
    "/employees/directory",
    response_model=PaginatedEnvelope[EmployeeDirectoryOut],
)
@limiter.limit("60/minute")
async def list_employee_directory(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[EmployeeSortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """Public — no bearer token, no permission check
    (security-architecture.md §2's public-endpoint posture, same rationale
    as `org_structure/router.py::list_branches`): the pre-registration form
    needs a "who are you visiting" picker before a visitor authenticates.

    Deliberately a separate route and schema from `GET /employees` rather
    than an unauthenticated mode of it: `EmployeeDirectoryOut` omits
    email/phone/employee_code, which `EmployeeOut` exposes to authenticated,
    permission-checked callers only. Every active `host`-role user, not
    branch/department scoped — see
    `auth/repository.py::UserRepository.list_hosts_page`.
    """
    page, page_size = pagination
    employees, total = await service.list_employee_directory(
        tenant_db, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    directory_outs = [await _to_employee_directory_out(e) for e in employees]
    return paginated_response(data=directory_outs, page=page, page_size=page_size, total=total)


def _to_role_out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        permission_codes=sorted(p.code for p in role.permissions),
        is_standard=role.name in STANDARD_ROLE_NAMES,
    )


@router.get(
    "/permissions",
    response_model=PaginatedEnvelope[PermissionOut],
    dependencies=[Depends(require_permission_anywhere("roles:view"))],
)
async def list_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[PermissionSortableField, Query(alias="sortBy")] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """The tenant-independent permission catalog, so a role-creation/update
    form can populate its permission-code choices instead of guessing —
    see `Requirement: Role Permission Codes Must Exist in the Catalog`.
    """
    page, page_size = pagination
    permissions, total = await service.list_permissions(
        db, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return paginated_response(
        data=[PermissionOut(code=p.code, description=p.description) for p in permissions],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/roles",
    response_model=Envelope[RoleOut],
    dependencies=[Depends(require_permission("roles:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    payload: RoleCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    role = await service.create_role(tenant_db, payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="role_created",
        entity_type="Role",
        entity_id=role.id,
        diff={"name": role.name, "permission_codes": [p.code for p in role.permissions]},
    )
    return success_response(data=_to_role_out(role), status_code=201)


@router.get(
    "/roles",
    response_model=PaginatedEnvelope[RoleOut],
    dependencies=[Depends(require_permission_anywhere("roles:view"))],
)
async def list_roles(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[RoleSortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    roles, total = await service.list_roles(
        tenant_db, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return paginated_response(
        data=[_to_role_out(r) for r in roles], page=page, page_size=page_size, total=total
    )


@router.get(
    "/roles/verify",
    response_model=Envelope[RoleVerifyResponse],
    dependencies=[Depends(require_permission_anywhere("roles:view"))],
)
async def verify_role_name(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    name: Annotated[str, Query(max_length=100)],
) -> JSONResponse:
    available = await service.verify_role_name(tenant_db, name)
    return success_response(data=RoleVerifyResponse(name=name, available=available))


@router.get(
    "/roles/{role_id}",
    response_model=Envelope[RoleOut],
    dependencies=[Depends(require_permission_anywhere("roles:view"))],
)
async def get_role(
    role_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    role = await service.get_role(tenant_db, role_id)
    return success_response(data=_to_role_out(role))


@router.put(
    "/roles/{role_id}",
    response_model=Envelope[RoleOut],
    dependencies=[Depends(require_permission("roles:manage"))],
)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    role = await service.update_role(tenant_db, role_id, payload)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="role_updated",
        entity_type="Role",
        entity_id=role.id,
        diff=payload.model_dump(exclude_unset=True, mode="json"),
    )
    return success_response(data=_to_role_out(role))


@router.delete(
    "/roles/{role_id}",
    dependencies=[Depends(require_permission("roles:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_role(
    role_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_role(tenant_db, role_id)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="role_deleted",
        entity_type="Role",
        entity_id=role_id,
    )


@router.post(
    "/roles/resync-permissions",
    response_model=Envelope[list[RolePermissionResyncEntryOut]],
    dependencies=[Depends(require_permission("roles:manage"))],
)
async def resync_role_permissions(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    actor: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Backfills any catalog-defined permission a standard role is
    currently missing (`add-invitation-approval-flow-and-role-resync/
    design.md` Decision 5) — fixes a tenant whose roles predate a
    permission being added to `rbac_catalog.py`, without a manual database
    edit. Additive only; never revokes a permission.
    """
    granted = await service.resync_role_permissions(tenant_db)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor.id,
        action="role_permissions_resynced",
        entity_type="Role",
        entity_id=None,
        diff=granted,
    )
    return success_response(
        data=[
            RolePermissionResyncEntryOut(role_name=name, granted_permission_codes=codes)
            for name, codes in sorted(granted.items())
        ]
    )
