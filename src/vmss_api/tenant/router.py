from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_db, get_tenant, require_permission
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository
from vmss_api.tenant.schemas import TenantOut, TenantSettingsUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get(
    "/me",
    response_model=Envelope[TenantOut],
    dependencies=[Depends(require_permission("tenants:read"))],
)
async def get_my_tenant(tenant: Annotated[Tenant, Depends(get_tenant)]) -> JSONResponse:
    return success_response(data=TenantOut.model_validate(tenant))


@router.patch(
    "/me/settings",
    response_model=Envelope[TenantOut],
    dependencies=[Depends(require_permission("tenants:update"))],
)
async def update_my_tenant_settings(
    body: TenantSettingsUpdate,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Per-tenant feature switches: the badge print flow (add-badge-print-flow)
    and zone access control (add-zone-access-control). Only the switches present
    in the body change. The tenant is the caller's own, from the token — never a
    path/body value."""
    changes = {
        name: value
        for name, value in (
            ("badge_print_flow_enabled", body.badge_print_flow_enabled),
            (
                "badge_print_requires_id_verification",
                body.badge_print_requires_id_verification,
            ),
            ("zone_access_enabled", body.zone_access_enabled),
        )
        if value is not None
    }
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No settings provided")
    previous = {name: getattr(tenant, name) for name in changes}
    updated = await TenantRepository(db).set_flags(tenant.id, **changes)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await db.commit()
    out = TenantOut.model_validate(updated)
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="tenant_settings_updated",
        entity_type="Tenant",
        entity_id=tenant.id,
        diff={name: {"before": previous[name], "after": value} for name, value in changes.items()},
    )
    return success_response(data=out)
