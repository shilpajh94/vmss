import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.security import decode_token
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_bearer_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """Decodes the bearer token only — no type check, no DB access. Shared
    building block for both the tenant-user chain (`get_token_payload`
    below) and superadmin auth (`platform/service.py::get_current_superadmin`),
    which carry different `type` claims and shouldn't accept each other's
    tokens.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def get_token_payload(
    payload: Annotated[dict[str, Any], Depends(get_bearer_payload)],
) -> dict[str, Any]:
    """Tenant and user resolution (`get_tenant`, `get_current_user` below)
    both derive from the claims this returns, never the other way around:
    under schema-per-tenant the `users` table can't be queried until the
    tenant's schema is already known, so the token (not a DB lookup) has to
    be the first hop.
    """
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")
    return payload


async def get_tenant(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """Resolves the caller's tenant from the access token's `tenant_id`
    claim, via the global `tenants` registry. See database-architecture.md §2.
    """
    raw_tenant_id = payload.get("tenant_id")
    if raw_tenant_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no tenant")
    tenant = await TenantRepository(db).get(uuid.UUID(raw_tenant_id))
    if tenant is None or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant not found or inactive"
        )
    return tenant


async def get_tenant_db(
    tenant: Annotated[Tenant, Depends(get_tenant)],
) -> AsyncGenerator[AsyncSession]:
    """Yields a session bound to the resolved tenant's own Postgres schema
    via `schema_translate_map` — see `core/database.py::get_tenant_session`.
    Every tenant-scoped repository call in a request goes through this.
    """
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session


async def get_current_user(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> User:
    """Loads the user from the resolved tenant's own schema.

    Sanctioned exception to "core doesn't depend on features": imports
    `User` from `vmss_api.auth.models` and `Tenant`/`TenantRepository` from
    `vmss_api.tenant` — authentication and tenant resolution are
    cross-cutting infrastructure every other feature needs. See
    fastapi-architecture.md §6.
    """
    user_id = uuid.UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    structlog.contextvars.bind_contextvars(user_id=str(user.id), tenant_id=payload["tenant_id"])
    return user


def require_permission(permission_code: str):
    """Dependency factory for RBAC checks. See security-architecture.md §1."""

    def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not user.has_permission(permission_code):
            logger.warning("permission_denied", permission_code=permission_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
            )
        return user

    return _check
