"""Tenant resolution for the public `GET /invitations/track` endpoint.

This endpoint carries no bearer token and no path-embedded token at all — a
visitor who lost their tracking ID is exactly who needs it — so it can't
resolve a tenant the way any authenticated endpoint does
(`core/tenancy.py::get_tenant`). See `track_default_tenant_db` below.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.tenant.repository import TenantRepository


async def track_default_tenant_db(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[AsyncSession]:
    """`GET /invitations/track` has no token and no tenant identifier at all
    to resolve from — a real hostname/slug-routed multi-tenant deployment
    would resolve it from the request's origin, but nothing in this codebase
    does that yet. Resolves the single configured `default_tenant_slug`
    (`database-architecture.md` §2: "today, exactly one row exists in
    `tenants`... always resolve it through get_tenant/get_tenant_db", applied
    here via the slug rather than a hardcoded id) — flagged as a known
    limitation to replace with real tenant routing once a second tenant
    exists and this endpoint needs to search across all of them.
    """
    tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session
