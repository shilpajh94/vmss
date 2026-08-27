"""Tenant resolution for visitor-categories' public listing endpoint — the
pre-registration form needs to render a category picker before a visitor
authenticates, same rationale as `org_structure/deps.py::public_tenant_db`
(`fix-public-org-listings-and-email-diagnostics/design.md` Decision 1). Each
public-endpoint feature keeps its own copy of this dependency rather than a
shared one, matching `invitations/deps.py::track_default_tenant_db` and
`org_structure/deps.py::public_tenant_db`'s existing precedent.
"""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.security import decode_token
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_optional_bearer_scheme = HTTPBearer(auto_error=False)


async def _tenant_from_bearer_token(
    db: AsyncSession, credentials: HTTPAuthorizationCredentials
) -> Tenant | None:
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None
    if payload.get("type") != "access":
        return None
    raw_tenant_id = payload.get("tenant_id")
    if raw_tenant_id is None:
        return None
    try:
        tenant_id = UUID(raw_tenant_id)
    except ValueError:
        return None
    return await TenantRepository(db).get(tenant_id)


async def public_tenant_db(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer_scheme)
    ] = None,
) -> AsyncGenerator[AsyncSession]:
    """Prefers the caller's own tenant when a valid access token is
    presented, falling back to `settings.default_tenant_slug` otherwise —
    see `org_structure/deps.py::public_tenant_db`'s matching docstring for
    the full rationale.
    """
    tenant = await _tenant_from_bearer_token(db, credentials) if credentials is not None else None
    if tenant is None:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session
