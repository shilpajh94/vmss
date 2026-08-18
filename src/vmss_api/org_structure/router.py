import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
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
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import Envelope, PaginatedEnvelope, SortOrder
from vmss_api.org_structure import service
from vmss_api.org_structure.deps import require_branch_permission
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
    dependencies=[Depends(require_permission("branches:view"))],
)
async def list_branches(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    branches, total = await service.list_branches_page(
        tenant_db, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
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
    dependencies=[Depends(require_permission("branches:view"))],
)
async def get_branch(
    branch_id: uuid.UUID, tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)]
) -> JSONResponse:
    branch = await service.get_branch(tenant_db, branch_id)
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
# Branch-scoped: `X-Branch-ID` required (`require_branch_permission`); the
# service layer rejects (404) any building not actually belonging to that
# branch. See org_structure/service.py's module docstring.


@building_router.post("", response_model=Envelope[BuildingOut], status_code=status.HTTP_201_CREATED)
async def create_building(
    payload: BuildingCreate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("buildings:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    building = await service.create_building(tenant_db, payload, branch.id)
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
async def list_buildings(
    branch: Annotated[Branch, Depends(require_branch_permission("buildings:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    buildings, total = await service.list_buildings_page(
        tenant_db,
        authorized_branch_id=branch.id,
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
    branch: Annotated[Branch, Depends(require_branch_permission("buildings:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    building = await service.get_building(tenant_db, building_id, branch.id)
    return success_response(data=BuildingOut.model_validate(building))


@building_router.put("/{building_id}", response_model=Envelope[BuildingOut])
async def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("buildings:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    building = await service.update_building(tenant_db, building_id, payload, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("buildings:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_building(tenant_db, building_id, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("floors:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    floor = await service.create_floor(tenant_db, payload, branch.id)
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
async def list_floors(
    branch: Annotated[Branch, Depends(require_branch_permission("floors:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    building_id: Annotated[uuid.UUID | None, Query(alias="buildingId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    floors, total = await service.list_floors_page(
        tenant_db,
        authorized_branch_id=branch.id,
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
    branch: Annotated[Branch, Depends(require_branch_permission("floors:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    floor = await service.get_floor(tenant_db, floor_id, branch.id)
    return success_response(data=FloorOut.model_validate(floor))


@floor_router.put("/{floor_id}", response_model=Envelope[FloorOut])
async def update_floor(
    floor_id: uuid.UUID,
    payload: FloorUpdate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("floors:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    floor = await service.update_floor(tenant_db, floor_id, payload, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("floors:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_floor(tenant_db, floor_id, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("departments:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    department = await service.create_department(tenant_db, payload, branch.id)
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
async def list_departments(
    branch: Annotated[Branch, Depends(require_branch_permission("departments:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    floor_id: Annotated[uuid.UUID | None, Query(alias="floorId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    departments, total = await service.list_departments_page(
        tenant_db,
        authorized_branch_id=branch.id,
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
    branch: Annotated[Branch, Depends(require_branch_permission("departments:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    department = await service.get_department(tenant_db, department_id, branch.id)
    return success_response(data=DepartmentOut.model_validate(department))


@department_router.put("/{department_id}", response_model=Envelope[DepartmentOut])
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("departments:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    department = await service.update_department(tenant_db, department_id, payload, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("departments:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_department(tenant_db, department_id, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("desks:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    desk = await service.create_reception_desk(tenant_db, payload, branch.id)
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
async def list_reception_desks(
    branch: Annotated[Branch, Depends(require_branch_permission("desks:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    floor_id: Annotated[uuid.UUID | None, Query(alias="floorId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    desks, total = await service.list_reception_desks_page(
        tenant_db,
        authorized_branch_id=branch.id,
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
    branch: Annotated[Branch, Depends(require_branch_permission("desks:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    desk = await service.get_reception_desk(tenant_db, desk_id, branch.id)
    return success_response(data=ReceptionDeskOut.model_validate(desk))


@desk_router.put("/{desk_id}", response_model=Envelope[ReceptionDeskOut])
async def update_reception_desk(
    desk_id: uuid.UUID,
    payload: ReceptionDeskUpdate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("desks:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    desk = await service.update_reception_desk(tenant_db, desk_id, payload, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("desks:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_reception_desk(tenant_db, desk_id, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("gates:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    gate = await service.create_security_gate(tenant_db, payload, branch.id)
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
async def list_security_gates(
    branch: Annotated[Branch, Depends(require_branch_permission("gates:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    building_id: Annotated[uuid.UUID | None, Query(alias="buildingId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    gates, total = await service.list_security_gates_page(
        tenant_db,
        authorized_branch_id=branch.id,
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
    branch: Annotated[Branch, Depends(require_branch_permission("gates:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    gate = await service.get_security_gate(tenant_db, gate_id, branch.id)
    return success_response(data=SecurityGateOut.model_validate(gate))


@gate_router.put("/{gate_id}", response_model=Envelope[SecurityGateOut])
async def update_security_gate(
    gate_id: uuid.UUID,
    payload: SecurityGateUpdate,
    background_tasks: BackgroundTasks,
    branch: Annotated[Branch, Depends(require_branch_permission("gates:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    gate = await service.update_security_gate(tenant_db, gate_id, payload, branch.id)
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
    branch: Annotated[Branch, Depends(require_branch_permission("gates:manage"))],
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.delete_security_gate(tenant_db, gate_id, branch.id)
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
