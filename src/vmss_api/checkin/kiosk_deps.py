"""Context for the kiosk badge routes: flag gate, default tenant, usable kiosk
device. One dependency so the order is fixed — flag off is a `404` before any
device check, and a bad device never reaches a tenant-scoped query."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.tenancy import DefaultTenantUnresolved, TenantContext, resolve_default_tenant
from vmss_api.devices import service as device_service
from vmss_api.devices.models import Device


@dataclass(frozen=True)
class KioskContext:
    tenant: TenantContext
    tenant_db: AsyncSession
    device: Device


async def get_kiosk_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: Annotated[
        str | None,
        Header(
            alias="device-id",
            max_length=255,
            description=(
                "Required. The registered kiosk performing the action; must be "
                "approved, enabled and in `kiosk` operating mode. No bearer token is used."
            ),
        ),
    ] = None,
) -> AsyncGenerator[KioskContext]:
    try:
        tenant = await resolve_default_tenant(db)
    except DefaultTenantUnresolved as exc:
        logger.error("kiosk_default_tenant_unconfigured", reason=exc.reason)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive"
        ) from exc
    if not tenant.badge_print_flow_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    context = TenantContext(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        schema_name=tenant.schema_name,
        is_active=tenant.is_active,
        timezone=tenant.timezone,
        badge_print_flow_enabled=tenant.badge_print_flow_enabled,
    )
    async with tenant_session_scope(tenant.schema_name) as tenant_db:
        device = await device_service.resolve_usable_kiosk(tenant_db, device_id)
        yield KioskContext(tenant=context, tenant_db=tenant_db, device=device)
