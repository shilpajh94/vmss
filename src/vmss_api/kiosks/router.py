import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status
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
from vmss_api.core.schemas import Envelope, PaginatedEnvelope, SortOrder
from vmss_api.kiosks import service
from vmss_api.kiosks.schemas import (
    KioskCreate,
    KioskOut,
    KioskUpdate,
    KioskVisibilityUpdate,
    SortableField,
)
from vmss_api.org_structure.deps import public_tenant_db
from vmss_api.org_structure.schemas import ActiveStatus
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/kiosks", tags=["kiosks"])


def _queue_audit(
    background_tasks: BackgroundTasks,
    tenant: Tenant,
    user: User,
    *,
    action: str,
    entity_id: uuid.UUID,
) -> None:
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action=action,
        entity_type="Kiosk",
        entity_id=entity_id,
    )


@router.post(
    "",
    response_model=Envelope[KioskOut],
    dependencies=[Depends(require_permission("kiosks:manage"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_kiosk(
    payload: KioskCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    kiosk = await service.create_kiosk(tenant_db, payload)
    _queue_audit(background_tasks, tenant, user, action="kiosk_created", entity_id=kiosk.id)
    return success_response(
        data=KioskOut.model_validate(kiosk), status_code=status.HTTP_201_CREATED
    )


@router.get(
    "",
    response_model=PaginatedEnvelope[KioskOut],
)
@limiter.limit("60/minute")
async def list_kiosks(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    kiosk_status: Annotated[ActiveStatus | None, Query(alias="status")] = None,
    include_hidden: Annotated[bool, Query(alias="includeHidden")] = False,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "name",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    kiosks, total = await service.list_kiosks_page(
        tenant_db,
        status=kiosk_status,
        include_hidden=include_hidden,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[KioskOut.model_validate(k) for k in kiosks],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{kiosk_id}",
    response_model=Envelope[KioskOut],
)
@limiter.limit("60/minute")
async def get_kiosk(
    request: Request,
    kiosk_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
) -> JSONResponse:
    kiosk = await service.get_kiosk(tenant_db, kiosk_id)
    return success_response(data=KioskOut.model_validate(kiosk))


@router.put(
    "/{kiosk_id}",
    response_model=Envelope[KioskOut],
    dependencies=[Depends(require_permission("kiosks:manage"))],
)
async def update_kiosk(
    kiosk_id: uuid.UUID,
    payload: KioskUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    kiosk = await service.update_kiosk(tenant_db, kiosk_id, payload)
    _queue_audit(background_tasks, tenant, user, action="kiosk_updated", entity_id=kiosk.id)
    return success_response(data=KioskOut.model_validate(kiosk))


@router.patch(
    "/{kiosk_id}/visibility",
    response_model=Envelope[KioskOut],
    dependencies=[Depends(require_permission("kiosks:manage"))],
)
async def set_kiosk_visibility(
    kiosk_id: uuid.UUID,
    payload: KioskVisibilityUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    kiosk = await service.set_visibility(tenant_db, kiosk_id, payload.is_hidden)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="kiosk_hidden" if kiosk.is_hidden else "kiosk_unhidden",
        entity_id=kiosk.id,
    )
    return success_response(data=KioskOut.model_validate(kiosk))


@router.delete(
    "/{kiosk_id}",
    dependencies=[Depends(require_permission("kiosks:manage"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_kiosk(
    kiosk_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await service.delete_kiosk(tenant_db, kiosk_id)
    _queue_audit(background_tasks, tenant, user, action="kiosk_deleted", entity_id=kiosk_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
