import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any, Literal

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope
from vmss_api.core.security import decode_token
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_bearer_scheme = HTTPBearer(auto_error=False)


class DefaultTenantUnresolved(Exception):
    """Raised by `resolve_default_tenant` when `settings.default_tenant_slug`
    doesn't resolve to an active tenant. Every public, unauthenticated
    endpoint that falls back to this single configured tenant
    (`registrations`, `identity_verification`, `invitations`' tracking
    lookup) catches this and translates it into its own existing status
    code/message — this exception only centralizes detection, not the
    response shape, which legitimately differs per caller.
    """

    def __init__(self, reason: Literal["not_found", "inactive"]) -> None:
        self.reason = reason
        super().__init__(reason)


async def resolve_default_tenant(db: AsyncSession) -> Tenant:
    """Resolves `settings.default_tenant_slug` to an active tenant — the
    shared lookup behind every public endpoint that has no caller-supplied
    tenant identifier to resolve from instead. Raises `DefaultTenantUnresolved`
    rather than an `HTTPException` so each caller keeps its own existing
    status code and message; only the lookup and its `reason` classification
    (missing row vs. inactive row) are shared, per
    `logging-observability.md` §3's requirement that a caller distinguish
    the two when logging a server-side misconfiguration.
    """
    tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None:
        raise DefaultTenantUnresolved(reason="not_found")
    if not tenant.is_active:
        raise DefaultTenantUnresolved(reason="inactive")
    return tenant


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


def branch_filter(column: Any, branch_scope: BranchScope) -> Any | None:
    """Translates a resolved `BranchScope` into a filter clause: `None` (no
    filter at all) for a company-wide "all" scope, otherwise `column IN
    (...)` — a single-branch scope is just a one-element set, so there's no
    separate equality-filter path to maintain. See
    `org_structure/deps.py::require_branch_scope`.
    """
    return None if branch_scope == "all" else column.in_(branch_scope)
