import uuid
from typing import Annotated, Any

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
from vmss_api.core.logging import logger
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import Envelope, PaginatedEnvelope, SortOrder
from vmss_api.devices import service
from vmss_api.devices.schemas import (
    ApprovalStatus,
    DeviceApprovalStatusOut,
    DeviceOut,
    DeviceRegister,
    DeviceRegistrationOut,
    KioskLocationValidationSetting,
    OperatingMode,
    SortableField,
)
from vmss_api.invitations.deps import track_default_tenant, track_default_tenant_db
from vmss_api.org_structure.schemas import ActiveStatus
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/devices", tags=["devices"])


def _require(permission_code: str) -> list[Any]:
    """`get_tenant` first, then the permission check — the same order production
    resolves them in (`get_current_user` -> `get_tenant_db` -> `get_tenant`).
    `get_tenant` rolls back its session, so under the tests' shared session it
    would otherwise expire the already-loaded user mid-request."""
    return [Depends(get_tenant), Depends(require_permission(permission_code))]


settings_router = APIRouter(prefix="/admin/settings", tags=["devices"])


def _queue_audit(
    background_tasks: BackgroundTasks,
    tenant: Tenant,
    actor_user_id: uuid.UUID | None,
    *,
    action: str,
    entity_id: uuid.UUID,
    entity_type: str = "Device",
) -> None:
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
    )


# Declared before the `/{device_pk}` routes so `register` isn't parsed as a UUID.
@router.post(
    "/register",
    response_model=Envelope[DeviceRegistrationOut],
)
@limiter.limit("10/minute")
async def register_device(
    request: Request,
    payload: DeviceRegister,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(track_default_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
) -> JSONResponse:
    """Public device self-registration from the mobile app. Creates a
    pending, disabled device; an existing `deviceId` returns its current
    status unchanged (201 when created, 200 otherwise)."""
    device, created = await service.register_device(tenant_db, payload)
    if created:
        logger.info("device_registered", device_pk=str(device.id))
        _queue_audit(
            background_tasks, tenant, None, action="device_registered", entity_id=device.id
        )
    return success_response(
        data=DeviceRegistrationOut.model_validate(device),
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


# Declared before the `/{device_pk}` routes so `approval-status` isn't parsed as a UUID.
@router.get(
    "/approval-status",
    response_model=Envelope[DeviceApprovalStatusOut],
)
@limiter.limit("60/minute")
async def get_device_approval_status(
    request: Request,
    tenant_db: Annotated[AsyncSession, Depends(track_default_tenant_db)],
    device_id: Annotated[str, Query(alias="deviceId", min_length=1, max_length=255)],
) -> JSONResponse:
    """Public, read-only: has this device's registration been approved?
    404 when the `deviceId` is unknown (never registered or deleted)."""
    return success_response(data=await service.get_device_approval_status(tenant_db, device_id))


@router.get(
    "",
    response_model=PaginatedEnvelope[DeviceOut],
    dependencies=_require("devices:view"),
)
async def list_devices(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    approval_status: Annotated[ApprovalStatus | None, Query(alias="approvalStatus")] = None,
    device_status: Annotated[ActiveStatus | None, Query(alias="status")] = None,
    operating_mode: Annotated[OperatingMode | None, Query(alias="operatingMode")] = None,
    branch_id: Annotated[uuid.UUID | None, Query(alias="branchId")] = None,
    building_id: Annotated[uuid.UUID | None, Query(alias="buildingId")] = None,
    sort_by: Annotated[SortableField, Query(alias="sortBy")] = "created_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
) -> JSONResponse:
    page, page_size = pagination
    devices, total = await service.list_devices_page(
        tenant_db,
        approval_status=approval_status,
        is_active=None if device_status is None else device_status == ActiveStatus.active,
        operating_mode=operating_mode,
        branch_id=branch_id,
        building_id=building_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(data=devices, page=page, page_size=page_size, total=total)


@router.get(
    "/{device_pk}",
    response_model=Envelope[DeviceOut],
    dependencies=_require("devices:view"),
)
async def get_device(
    device_pk: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    return success_response(data=await service.get_device_out(tenant_db, device_pk))


@router.post(
    "/{device_pk}/approve",
    response_model=Envelope[DeviceOut],
    dependencies=_require("devices:approve"),
)
async def approve_device(
    device_pk: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    actor_id = user.id
    device, changed = await service.approve_device(tenant_db, device_pk, approver_id=actor_id)
    if changed:
        _queue_audit(
            background_tasks, tenant, actor_id, action="device_approved", entity_id=device.id
        )
    return success_response(data=device)


@router.post(
    "/{device_pk}/enable",
    response_model=Envelope[DeviceOut],
    dependencies=_require("devices:manage"),
)
async def enable_device(
    device_pk: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    actor_id = user.id
    device, changed = await service.set_device_active(tenant_db, device_pk, active=True)
    if changed:
        _queue_audit(
            background_tasks, tenant, actor_id, action="device_enabled", entity_id=device.id
        )
    return success_response(data=device)


@router.post(
    "/{device_pk}/disable",
    response_model=Envelope[DeviceOut],
    dependencies=_require("devices:manage"),
)
async def disable_device(
    device_pk: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    actor_id = user.id
    device, changed = await service.set_device_active(tenant_db, device_pk, active=False)
    if changed:
        _queue_audit(
            background_tasks, tenant, actor_id, action="device_disabled", entity_id=device.id
        )
    return success_response(data=device)


@router.delete(
    "/{device_pk}",
    dependencies=_require("devices:manage"),
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_device(
    device_pk: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    actor_id = user.id
    await service.delete_device(tenant_db, device_pk)
    _queue_audit(background_tasks, tenant, actor_id, action="device_deleted", entity_id=device_pk)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@settings_router.get(
    "/kiosk-location-validation",
    response_model=Envelope[KioskLocationValidationSetting],
    dependencies=_require("settings:view"),
)
async def get_kiosk_location_validation(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    enabled = await service.get_enforce_location_validation(tenant_db)
    return success_response(
        data=KioskLocationValidationSetting(enforce_kiosk_location_validation=enabled)
    )


@settings_router.put(
    "/kiosk-location-validation",
    response_model=Envelope[KioskLocationValidationSetting],
    dependencies=_require("settings:manage"),
)
async def set_kiosk_location_validation(
    payload: KioskLocationValidationSetting,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    actor_id = user.id
    enabled = await service.set_enforce_location_validation(
        tenant_db, payload.enforce_kiosk_location_validation
    )
    _queue_audit(
        background_tasks,
        tenant,
        actor_id,
        action="kiosk_location_validation_updated",
        entity_id=tenant.id,
        entity_type="TenantSettings",
    )
    return success_response(
        data=KioskLocationValidationSetting(enforce_kiosk_location_validation=enabled)
    )
