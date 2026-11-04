from typing import Annotated

from fastapi import Depends, HTTPException, status

from vmss_api.core.tenancy import TenantContext, get_tenant


async def require_zone_access_enabled(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> None:
    """`404`, not `403`, unless this tenant's `zone_access_enabled` toggle is on
    (`PATCH /tenants/me/settings`), so a disabled feature is indistinguishable
    from a route that doesn't exist. A missing permission stays a `403`."""
    if not tenant.zone_access_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
