import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import (
    get_current_user,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_permission,
)
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.org_structure import service
from vmss_api.org_structure.deps import (
    authorize_branch_id,
    public_branch_scope,
    public_tenant_db,
    require_branch_permission,
)
from vmss_api.org_structure.models import Branch
from vmss_api.org_structure.schemas import (
    BranchCreate,
    BranchOut,
    BranchProvisionRequest,
    BranchProvisionResponse,
    BranchUpdate,
    BuildingCreate,
    BuildingOut,
    BuildingUpdate,
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    FloorCreate,
    FloorOut,
    FloorUpdate,
    ReceptionDeskCreate,
    ReceptionDeskOut,
    ReceptionDeskUpdate,
    SecurityGateCreate,
    SecurityGateOut,
    SecurityGateUpdate,
    SortableField,
)
from vmss_api.tenant.models import Tenant

router = APIRouter(tags=["org-structure"])

company_router = APIRouter(prefix="/company")
branch_router = APIRouter(prefix="/branches")
building_router = APIRouter(prefix="/buildings")
floor_router = APIRouter(prefix="/floors")
department_router = APIRouter(prefix="/departments")
desk_router = APIRouter(prefix="/reception-desks")
gate_router = APIRouter(prefix="/security-gates")


def _queue_audit(
    background_tasks: BackgroundTasks,
    tenant: Tenant,
    user: User,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    """Queues one `AuditLog` write (security-architecture.md §5) as a
    background task so it never blocks the response — see `auth/audit.py`.
    """
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
    )


# --- Company (singleton) -----------------------------------------------
#
# Company-wide only, not branch-scoped: the company profile sits above the
# branch level in the org chart (Company -> Branch -> Building -> ...), same
# as Branch CRUD itself below.


@company_router.post(
    "",
    response_model=Envelope[CompanyOut],
    dependencies=[Depends(require_permission("companies:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    payload: CompanyCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    company = await service.create_company(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="company_created",
        entity_type="Company",
        entity_id=company.id,
    )
    return success_response(
        data=CompanyOut.model_validate(company), status_code=status.HTTP_201_CREATED
    )


@company_router.get(
    "",
    response_model=Envelope[CompanyOut],
    dependencies=[Depends(require_permission("companies:view"))],
)
async def get_company(tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]) -> JSONResponse:
    company = await service.get_company(tenant_db)
    return success_response(data=CompanyOut.model_validate(company))


@company_router.put(
    "",
    response_model=Envelope[CompanyOut],
    dependencies=[Depends(require_permission("companies:manage"))],
)
async def update_company(
    payload: CompanyUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    company = await service.update_company(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="company_updated",
        entity_type="Company",
        entity_id=company.id,
    )
    return success_response(data=CompanyOut.model_validate(company))


@company_router.delete(
    "",
    dependencies=[Depends(require_permission("companies:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_company(
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    company = await service.get_company(tenant_db)
    await service.delete_company(tenant_db)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="company_deleted",
        entity_type="Company",
        entity_id=company.id,
    )


# --- Branch --------------------------------------------------------------
#
# Company-wide only, not branch-scoped: you can't be "scoped to a branch" to
# create/manage the branches themselves.


@branch_router.post(
    "",
    response_model=Envelope[BranchOut],
    dependencies=[Depends(require_permission("branches:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_branch(
    payload: BranchCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    branch = await service.create_branch(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="branch_created",
        entity_type="Branch",
        entity_id=branch.id,
    )
    return success_response(
        data=BranchOut.model_validate(branch), status_code=status.HTTP_201_CREATED
    )


@branch_router.get(
    "",
    response_model=PaginatedEnvelope[BranchOut],
)
@limiter.limit("60/minute")
async def list_branches(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    """Public — no bearer token, no permission check (security-architecture.md
    §2's public-endpoint posture, applied here per
    `fix-public-org-listings-and-email-diagnostics/design.md` Decision 1).
    `X-Branch-ID` narrows to one branch when supplied; every branch's rows
    are returned otherwise.
    """
    page, page_size = pagination
    branches, total = await service.list_branches_page(
        tenant_db,
        branch_scope=branch_scope,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[BranchOut.model_validate(b) for b in branches],
        page=page,
        page_size=page_size,
        total=total,
    )


@branch_router.post(
    "/provision",
    response_model=Envelope[BranchProvisionResponse],
    dependencies=[Depends(require_permission("branches:provision"))],
    status_code=status.HTTP_201_CREATED,
)
async def provision_branch(
    payload: BranchProvisionRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Bulk bootstrap: creates a `Branch` plus as much of its Building ->
    Floor -> Department/ReceptionDesk chain and SecurityGates as the payload
    supplies, in one transaction — the net-new capability on top of plain
    `POST /branches`, which only ever creates the bare branch row. Gated by
    its own `branches:provision` permission (granted to Admin only) rather
    than reusing `branches:manage`, since standing up a whole location's org
    chart in one call is a materially bigger blast radius than renaming one
    branch.
    """
    branch, counts = await service.provision_branch(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="branch_provisioned",
        entity_type="Branch",
        entity_id=branch.id,
    )
    return success_response(
        data=BranchProvisionResponse(
            branch=BranchOut.model_validate(branch),
            buildings_created=counts.buildings,
            floors_created=counts.floors,
            departments_created=counts.departments,
            reception_desks_created=counts.reception_desks,
            security_gates_created=counts.security_gates,
        ),
        status_code=status.HTTP_201_CREATED,
    )


@branch_router.get("/current", response_model=Envelope[BranchOut])
async def get_current_branch(
    branch: Annotated[Branch, Depends(require_branch_permission("branches:view"))],
) -> JSONResponse:
    """Resolves the branch a client is currently scoped to via the
    `X-Branch-ID` header — lets a client confirm branch context and access
    right after branch selection, before sending that header on subsequent
    branch-scoped requests.
    """
    return success_response(data=BranchOut.model_validate(branch))


@branch_router.get(
    "/{branch_id}",
    response_model=Envelope[BranchOut],
)
async def get_branch(
    branch_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    branch = await service.get_branch(tenant_db, branch_id, user, "branches:view")
    return success_response(data=BranchOut.model_validate(branch))


@branch_router.put(
    "/{branch_id}",
    response_model=Envelope[BranchOut],
    dependencies=[Depends(require_permission("branches:manage"))],
)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    branch = await service.update_branch(tenant_db, branch_id, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="branch_updated",
        entity_type="Branch",
        entity_id=branch.id,
    )
    return success_response(data=BranchOut.model_validate(branch))


@branch_router.delete(
    "/{branch_id}",
    dependencies=[Depends(require_permission("branches:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_branch(
    branch_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_branch(tenant_db, branch_id)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="branch_deleted",
        entity_type="Branch",
        entity_id=branch_id,
    )


# --- Building --------------------------------------------------------------
#
# Branch-scoped: `X-Branch-ID` is optional everywhere. Creation resolves its
# branch from `payload.branchId`; list scopes to every branch the caller is
# authorized for when the header is omitted; get/update/delete authorize
# against the target building's own branch. See
# org_structure/service.py's module docstring.


@building_router.post("", response_model=Envelope[BuildingOut], status_code=status.HTTP_201_CREATED)
async def create_building(
    payload: BuildingCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    await authorize_branch_id(tenant_db, user, "buildings:manage", payload.branch_id)
    building = await service.create_building(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="building_created",
        entity_type="Building",
        entity_id=building.id,
    )
    return success_response(
        data=BuildingOut.model_validate(building), status_code=status.HTTP_201_CREATED
    )


@building_router.get("", response_model=PaginatedEnvelope[BuildingOut])
@limiter.limit("60/minute")
async def list_buildings(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    buildings, total = await service.list_buildings_page(
        tenant_db,
        branch_scope=branch_scope,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[BuildingOut.model_validate(b) for b in buildings],
        page=page,
        page_size=page_size,
        total=total,
    )


@building_router.get("/{building_id}", response_model=Envelope[BuildingOut])
async def get_building(
    building_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    building = await service.get_building(tenant_db, building_id, user, "buildings:view")
    return success_response(data=BuildingOut.model_validate(building))


@building_router.put("/{building_id}", response_model=Envelope[BuildingOut])
async def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    building = await service.update_building(tenant_db, building_id, payload, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="building_updated",
        entity_type="Building",
        entity_id=building.id,
    )
    return success_response(data=BuildingOut.model_validate(building))


@building_router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_building(
    building_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_building(tenant_db, building_id, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="building_deleted",
        entity_type="Building",
        entity_id=building_id,
    )


# --- Floor --------------------------------------------------------------
#
# Branch-scoped — see Building above.


@floor_router.post("", response_model=Envelope[FloorOut], status_code=status.HTTP_201_CREATED)
async def create_floor(
    payload: FloorCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    branch_id = await service.resolve_building_branch_id(tenant_db, payload.building_id)
    if branch_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Building not found")
    await authorize_branch_id(tenant_db, user, "floors:manage", branch_id)
    floor = await service.create_floor(tenant_db, payload, branch_id)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="floor_created",
        entity_type="Floor",
        entity_id=floor.id,
    )
    return success_response(
        data=FloorOut.model_validate(floor), status_code=status.HTTP_201_CREATED
    )


@floor_router.get("", response_model=PaginatedEnvelope[FloorOut])
@limiter.limit("60/minute")
async def list_floors(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    building_id: Annotated[uuid.UUID | None, Query(alias="buildingId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    floors, total = await service.list_floors_page(
        tenant_db,
        branch_scope=branch_scope,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[FloorOut.model_validate(f) for f in floors],
        page=page,
        page_size=page_size,
        total=total,
    )


@floor_router.get("/{floor_id}", response_model=Envelope[FloorOut])
async def get_floor(
    floor_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    floor = await service.get_floor(tenant_db, floor_id, user, "floors:view")
    return success_response(data=FloorOut.model_validate(floor))


@floor_router.put("/{floor_id}", response_model=Envelope[FloorOut])
async def update_floor(
    floor_id: uuid.UUID,
    payload: FloorUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    floor = await service.update_floor(tenant_db, floor_id, payload, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="floor_updated",
        entity_type="Floor",
        entity_id=floor.id,
    )
    return success_response(data=FloorOut.model_validate(floor))


@floor_router.delete("/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_floor(
    floor_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_floor(tenant_db, floor_id, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="floor_deleted",
        entity_type="Floor",
        entity_id=floor_id,
    )


# --- Department --------------------------------------------------------------
#
# Branch-scoped — see Building above.


@department_router.post(
    "", response_model=Envelope[DepartmentOut], status_code=status.HTTP_201_CREATED
)
async def create_department(
    payload: DepartmentCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    await authorize_branch_id(tenant_db, user, "departments:manage", payload.branch_id)
    department = await service.create_department(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="department_created",
        entity_type="Department",
        entity_id=department.id,
    )
    return success_response(
        data=DepartmentOut.model_validate(department), status_code=status.HTTP_201_CREATED
    )


@department_router.get("", response_model=PaginatedEnvelope[DepartmentOut])
@limiter.limit("60/minute")
async def list_departments(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    floor_id: Annotated[uuid.UUID | None, Query(alias="floorId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    departments, total = await service.list_departments_page(
        tenant_db,
        branch_scope=branch_scope,
        floor_id=floor_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[DepartmentOut.model_validate(d) for d in departments],
        page=page,
        page_size=page_size,
        total=total,
    )


@department_router.get("/{department_id}", response_model=Envelope[DepartmentOut])
async def get_department(
    department_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    department = await service.get_department(tenant_db, department_id, user, "departments:view")
    return success_response(data=DepartmentOut.model_validate(department))


@department_router.put("/{department_id}", response_model=Envelope[DepartmentOut])
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    department = await service.update_department(tenant_db, department_id, payload, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="department_updated",
        entity_type="Department",
        entity_id=department.id,
    )
    return success_response(data=DepartmentOut.model_validate(department))


@department_router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_department(tenant_db, department_id, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="department_deleted",
        entity_type="Department",
        entity_id=department_id,
    )


# --- Reception Desk --------------------------------------------------------------
#
# Branch-scoped — see Building above.


@desk_router.post(
    "", response_model=Envelope[ReceptionDeskOut], status_code=status.HTTP_201_CREATED
)
async def create_reception_desk(
    payload: ReceptionDeskCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    branch_id = await service.resolve_floor_branch_id(tenant_db, payload.floor_id)
    if branch_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Floor not found")
    await authorize_branch_id(tenant_db, user, "desks:manage", branch_id)
    desk = await service.create_reception_desk(tenant_db, payload, branch_id)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="reception_desk_created",
        entity_type="ReceptionDesk",
        entity_id=desk.id,
    )
    return success_response(
        data=ReceptionDeskOut.model_validate(desk), status_code=status.HTTP_201_CREATED
    )


@desk_router.get("", response_model=PaginatedEnvelope[ReceptionDeskOut])
@limiter.limit("60/minute")
async def list_reception_desks(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    floor_id: Annotated[uuid.UUID | None, Query(alias="floorId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    desks, total = await service.list_reception_desks_page(
        tenant_db,
        branch_scope=branch_scope,
        floor_id=floor_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[ReceptionDeskOut.model_validate(d) for d in desks],
        page=page,
        page_size=page_size,
        total=total,
    )


@desk_router.get("/{desk_id}", response_model=Envelope[ReceptionDeskOut])
async def get_reception_desk(
    desk_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    desk = await service.get_reception_desk(tenant_db, desk_id, user, "desks:view")
    return success_response(data=ReceptionDeskOut.model_validate(desk))


@desk_router.put("/{desk_id}", response_model=Envelope[ReceptionDeskOut])
async def update_reception_desk(
    desk_id: uuid.UUID,
    payload: ReceptionDeskUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    desk = await service.update_reception_desk(tenant_db, desk_id, payload, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="reception_desk_updated",
        entity_type="ReceptionDesk",
        entity_id=desk.id,
    )
    return success_response(data=ReceptionDeskOut.model_validate(desk))


@desk_router.delete("/{desk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reception_desk(
    desk_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_reception_desk(tenant_db, desk_id, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="reception_desk_deleted",
        entity_type="ReceptionDesk",
        entity_id=desk_id,
    )


# --- Security Gate --------------------------------------------------------------
#
# Branch-scoped — see Building above.


@gate_router.post("", response_model=Envelope[SecurityGateOut], status_code=status.HTTP_201_CREATED)
async def create_security_gate(
    payload: SecurityGateCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    await authorize_branch_id(tenant_db, user, "gates:manage", payload.branch_id)
    gate = await service.create_security_gate(tenant_db, payload)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="security_gate_created",
        entity_type="SecurityGate",
        entity_id=gate.id,
    )
    return success_response(
        data=SecurityGateOut.model_validate(gate), status_code=status.HTTP_201_CREATED
    )


@gate_router.get("", response_model=PaginatedEnvelope[SecurityGateOut])
@limiter.limit("60/minute")
async def list_security_gates(
    request: Request,
    branch_scope: Annotated[BranchScope, Depends(public_branch_scope)],
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    building_id: Annotated[uuid.UUID | None, Query(alias="buildingId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    gates, total = await service.list_security_gates_page(
        tenant_db,
        branch_scope=branch_scope,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[SecurityGateOut.model_validate(g) for g in gates],
        page=page,
        page_size=page_size,
        total=total,
    )


@gate_router.get("/{gate_id}", response_model=Envelope[SecurityGateOut])
async def get_security_gate(
    gate_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    gate = await service.get_security_gate(tenant_db, gate_id, user, "gates:view")
    return success_response(data=SecurityGateOut.model_validate(gate))


@gate_router.put("/{gate_id}", response_model=Envelope[SecurityGateOut])
async def update_security_gate(
    gate_id: uuid.UUID,
    payload: SecurityGateUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    gate = await service.update_security_gate(tenant_db, gate_id, payload, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="security_gate_updated",
        entity_type="SecurityGate",
        entity_id=gate.id,
    )
    return success_response(data=SecurityGateOut.model_validate(gate))


@gate_router.delete("/{gate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_security_gate(
    gate_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_security_gate(tenant_db, gate_id, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="security_gate_deleted",
        entity_type="SecurityGate",
        entity_id=gate_id,
    )


router.include_router(company_router)
router.include_router(branch_router)
router.include_router(building_router)
router.include_router(floor_router)
router.include_router(department_router)
router.include_router(desk_router)
router.include_router(gate_router)
