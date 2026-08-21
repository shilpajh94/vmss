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

from vmss_api.core.config import settings
from vmss_api.core.database import get_db
from vmss_api.tenant.repository import TenantRepository


async def default_tenant_id(db: Annotated[AsyncSession, Depends(get_db)]) -> uuid.UUID:
    """Same known single-tenant limitation as `track_default_tenant_db` —
    replace with real hostname-based tenant routing once a second tenant
    exists.
    """
    tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    return tenant.id
