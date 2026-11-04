import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control import service
from vmss_api.access_control.decision import DenyReason
from vmss_api.access_control.deps import require_zone_access_enabled
from vmss_api.access_control.models import Zone
from vmss_api.access_control.schemas import (
    ScanOut,
    ScanRequest,
    ZoneCreate,
    ZoneIdsIn,
    ZoneIdsOut,
    ZoneOut,
    ZoneSortField,
    ZoneUpdate,
)
from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.deps import (
    get_current_user,
    get_pagination,
    get_tenant,
    get_tenant_db,
    require_permission,
    require_permission_anywhere,
)
from vmss_api.core.idempotency import Idempotency, idempotency
from vmss_api.core.logging import logger
from vmss_api.core.rate_limit import limiter
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.core.tenancy import TenantContext
from vmss_api.org_structure.deps import authorize_branch_id, require_branch_scope

# Full paths rather than a prefix: zones, scanning and the two mapping routes
# live under different resources but share one feature package. Every route is
# a 404 while the tenant's `zone_access_enabled` toggle is off.
router = APIRouter(tags=["access_control"], dependencies=[Depends(require_zone_access_enabled)])


def _zone_out(zone: Zone, gate_ids: list[uuid.UUID]) -> ZoneOut:
    out = ZoneOut.model_validate(zone)
    out.gate_ids = gate_ids
    return out


def _queue_audit(
    background_tasks: BackgroundTasks,
    tenant: TenantContext,
    user: User,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    diff: dict | None = None,
) -> None:
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        diff=diff,
    )


# --- zones ----------------------------------------------------------------------


@router.post(
    "/zones",
    response_model=Envelope[ZoneOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create a zone",
)
async def create_zone(
    payload: ZoneCreate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    await authorize_branch_id(tenant_db, user, "zones:manage", payload.branch_id)
    zone, gate_ids = await service.create_zone(tenant_db, payload)
    _queue_audit(
        background_tasks, tenant, user, action="zone_created", entity_type="Zone", entity_id=zone.id
    )
    return success_response(data=_zone_out(zone, gate_ids), status_code=status.HTTP_201_CREATED)


@router.get("/zones", response_model=PaginatedEnvelope[ZoneOut], summary="List zones")
async def list_zones(
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("zones:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    sort_by: Annotated[ZoneSortField, Query(alias="sortBy")] = ZoneSortField.name,
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.asc,
) -> JSONResponse:
    page, page_size = pagination
    rows, total = await service.list_zones_page(
        tenant_db,
        branch_scope=branch_scope,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by.value,
        sort_order=sort_order,
    )
    return paginated_response(
        data=[_zone_out(z, g) for z, g in rows], page=page, page_size=page_size, total=total
    )


@router.get("/zones/{zone_id}", response_model=Envelope[ZoneOut], summary="Get a zone")
async def get_zone(
    zone_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    zone, gate_ids = await service.get_zone(tenant_db, zone_id, user, "zones:view")
    return success_response(data=_zone_out(zone, gate_ids))


@router.put("/zones/{zone_id}", response_model=Envelope[ZoneOut], summary="Update a zone")
async def update_zone(
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    zone, gate_ids = await service.update_zone(tenant_db, zone_id, payload, user)
    _queue_audit(
        background_tasks, tenant, user, action="zone_updated", entity_type="Zone", entity_id=zone.id
    )
    return success_response(data=_zone_out(zone, gate_ids))


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a zone")
async def delete_zone(
    zone_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    zone = await service.delete_zone(tenant_db, zone_id, user)
    _queue_audit(
        background_tasks, tenant, user, action="zone_deleted", entity_type="Zone", entity_id=zone.id
    )


# --- allowed-zone mapping -----------------------------------------------------


@router.get(
    "/visitor-categories/{category_id}/zones",
    response_model=Envelope[ZoneIdsOut],
    summary="Default allowed zones of a visitor category",
)
async def get_category_zones(
    category_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    _: Annotated[User, Depends(require_permission_anywhere("zones:view"))],
) -> JSONResponse:
    return success_response(
        data=ZoneIdsOut(zone_ids=await service.get_category_zones(tenant_db, category_id))
    )


@router.put(
    "/visitor-categories/{category_id}/zones",
    response_model=Envelope[ZoneIdsOut],
    summary="Replace the default allowed zones of a visitor category",
)
async def set_category_zones(
    category_id: uuid.UUID,
    payload: ZoneIdsIn,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(require_permission("zones:manage"))],
) -> JSONResponse:
    zone_ids = await service.set_category_zones(tenant_db, category_id, payload.zone_ids)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="category_zones_updated",
        entity_type="VisitorCategory",
        entity_id=category_id,
        diff={"zone_ids": [str(z) for z in zone_ids]},
    )
    return success_response(data=ZoneIdsOut(zone_ids=zone_ids))


@router.get(
    "/invitations/{invitation_id}/zones",
    response_model=Envelope[ZoneIdsOut],
    summary="Zones reception allowed for one visit",
)
async def get_invitation_zones(
    invitation_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    return success_response(
        data=ZoneIdsOut(zone_ids=await service.get_invitation_zones(tenant_db, invitation_id, user))
    )


@router.put(
    "/invitations/{invitation_id}/zones",
    response_model=Envelope[ZoneIdsOut],
    summary="Replace the zones allowed for one visit (reception)",
)
async def set_invitation_zones(
    invitation_id: uuid.UUID,
    payload: ZoneIdsIn,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    zone_ids = await service.set_invitation_zones(tenant_db, invitation_id, payload.zone_ids, user)
    _queue_audit(
        background_tasks,
        tenant,
        user,
        action="invitation_zones_updated",
        entity_type="Invitation",
        entity_id=invitation_id,
        diff={"zone_ids": [str(z) for z in zone_ids]},
    )
    return success_response(data=ZoneIdsOut(zone_ids=zone_ids))


# --- gate scan ------------------------------------------------------------------


@router.post(
    "/access/scan",
    response_model=Envelope[ScanOut],
    summary="Scan a badge QR at a zone gate (entry or exit)",
)
@limiter.limit(settings.zone_scan_rate_limit)
async def scan_badge(
    request: Request,
    payload: ScanRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[TenantContext, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(require_permission_anywhere("access:scan"))],
    idem: Annotated[Idempotency, Depends(idempotency)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional. A retried scan with the same key logs one event.",
        ),
    ] = None,
) -> JSONResponse:
    """Authenticated (unlike the visitor-facing badge scans): the caller names
    the gate and zone, so possessing the token alone must not be enough."""
    cached = await idem.begin(
        tenant.id,
        "access_control",
        idempotency_key,
        caller=str(user.id),
        body=payload.model_dump_json(),
    )
    if cached is not None:
        return cached
    result = await service.scan(tenant_db, user=user, tenant=tenant, payload=payload)
    decision, visit, zone = result.decision, result.visit, result.zone
    if not decision.allowed and decision.reason is not None:
        logger.warning(
            "zone_entry_denied",
            invitation_id=str(visit.id),
            zone_id=str(zone.id),
            gate_id=str(result.gate_id),
            reason=decision.reason.value,
        )
        _queue_audit(
            background_tasks,
            tenant,
            user,
            action="zone_entry_denied",
            entity_type="Invitation",
            entity_id=visit.id,
            diff={
                "zone_id": str(zone.id),
                "gate_id": str(result.gate_id),
                "reason": decision.reason.value,
            },
        )
        background_tasks.add_task(
            service.alert_security_of_denial,
            tenant_id=tenant.id,
            tenant_schema=tenant.schema_name,
            branch_id=visit.branch_id,
            invitation_id=visit.id,
            zone_id=zone.id,
            zone_name=zone.name,
            reason=DenyReason(decision.reason),
        )
    else:
        logger.info(
            "zone_scan_allowed",
            invitation_id=str(visit.id),
            zone_id=str(zone.id),
            direction=result.direction.value,
        )
    response = success_response(
        data=ScanOut(
            allowed=decision.allowed,
            reason=decision.reason.value if decision.reason else None,
            visitor_name=visit.primary_contact_full_name,
        ),
        message="Access granted" if decision.allowed else "Access denied",
    )
    await idem.store(response)
    return response
