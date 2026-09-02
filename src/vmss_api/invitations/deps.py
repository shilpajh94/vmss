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

from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.tenancy import DefaultTenantUnresolved, resolve_default_tenant
from vmss_api.tenant.models import Tenant


async def track_default_tenant(db: Annotated[AsyncSession, Depends(get_db)]) -> Tenant:
    """Same `default_tenant_slug` resolution as `track_default_tenant_db`
    below, but returns the `Tenant` itself rather than a session bound to
    its schema — for callers that need `tenant.id`/`tenant.schema_name`
    directly (e.g. an idempotency cache key or an audit-log call) alongside
    a separately-injected `track_default_tenant_db` session, rather than a
    session with no way to recover which tenant it's bound to.
    """
    try:
        return await resolve_default_tenant(db)
    except DefaultTenantUnresolved as exc:
        logger.error("invitations_track_default_tenant_unconfigured", reason=exc.reason)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive"
        ) from exc


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

    An unresolvable default tenant is a server-side misconfiguration, not a
    property of the caller's request, so it's logged at `ERROR` distinguishing
    "no such tenant" from "tenant inactive" — same posture
    `registrations/deps.py`'s equivalent fallback already has
    (`logging-observability.md` §3). The client-facing 404 is unchanged.
    """
    try:
        tenant = await resolve_default_tenant(db)
    except DefaultTenantUnresolved as exc:
        logger.error("invitations_track_default_tenant_unconfigured", reason=exc.reason)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive"
        ) from exc
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session
