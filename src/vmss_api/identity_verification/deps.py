"""Tenant resolution for identity_verification's public endpoints.

Unlike `invitations/deps.py::track_default_tenant_db`, this feature never
touches a tenant-schema Postgres table (state is Redis-only — see
`add-identity-verification-otp/design.md`'s "Tenant resolution" decision),
so it only needs the tenant's id for the Redis key namespace, not a
tenant-bound session.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import get_db
from vmss_api.core.logging import logger
from vmss_api.core.tenancy import DefaultTenantUnresolved, resolve_default_tenant


async def default_tenant_id(db: Annotated[AsyncSession, Depends(get_db)]) -> uuid.UUID:
    """Same known single-tenant limitation as `track_default_tenant_db` —
    replace with real hostname-based tenant routing once a second tenant
    exists.

    An unresolvable default tenant is a server-side misconfiguration, not a
    property of the caller's request, so it's logged at `ERROR` distinguishing
    "no such tenant" from "tenant inactive" — same posture
    `registrations/deps.py`'s equivalent fallback already has
    (`logging-observability.md` §3). The client-facing 404 is unchanged.
    """
    try:
        tenant = await resolve_default_tenant(db)
    except DefaultTenantUnresolved as exc:
        logger.error("identity_verification_default_tenant_unconfigured", reason=exc.reason)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive"
        ) from exc
    return tenant.id
