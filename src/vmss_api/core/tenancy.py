```python
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TenantContext:
    """Tenant data safe to use after the registry session ends."""

    id: uuid.UUID
    schema_name: str
    is_active: bool
    timezone: str


class DefaultTenantUnresolved(Exception):
    """Raised when the configured default tenant is missing or inactive."""

    def __init__(self, reason: Literal["not_found", "inactive"]) -> None:
        self.reason = reason
        super().__init__(reason)


async def resolve_default_tenant(db: AsyncSession) -> Tenant:
    """Resolve the configured default tenant from the global registry."""
    tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)

    if tenant is None:
        raise DefaultTenantUnresolved(reason="not_found")

    if not tenant.is_active:
        raise DefaultTenantUnresolved(reason="inactive")

    return tenant


async def get_bearer_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> dict[str, Any]:
    """Decode the bearer token without database access."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return decode_token(credentials.credentials)


async def get_token_payload(
    payload: Annotated[dict[str, Any], Depends(get_bearer_payload)],
) -> dict[str, Any]:
    """Validate that the decoded token is an access token."""
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token",
        )

    return payload


async def get_tenant(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantContext:
    """Resolve a tenant and copy required values before rollback."""
    raw_tenant_id = payload.get("tenant_id")

    if raw_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no tenant",
        )

    try:
        tenant_id = uuid.UUID(raw_tenant_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant ID",
        ) from None

    try:
        tenant = await TenantRepository(db).get(tenant_id)

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found or inactive",
            )

        # Copy ORM values while the registry session is active.
        tenant_context = TenantContext(
            id=tenant.id,
            schema_name=tenant.schema_name,
            is_active=tenant.is_active,
            timezone=tenant.timezone,
        )

    finally:
        # Release the registry transaction before tenant-scoped DB work.
        await db.rollback()

    if not tenant_context.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found or inactive",
        )

    return tenant_context


async def get_tenant_db(
    tenant: Annotated[TenantContext, Depends(get_tenant)],
) -> AsyncGenerator[AsyncSession]:
    """Provide a session scoped to the tenant's database schema."""
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session


async def get_current_user(
    payload: Annotated[dict[str, Any], Depends(get_token_payload)],
    db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> User:
    """Load the authenticated user from the tenant's schema."""
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        ) from None

    stmt = select(User).where(
        User.id == user_id,
        User.deleted_at.is_(None),
    )

    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    structlog.contextvars.bind_contextvars(
        user_id=str(user.id),
        tenant_id=payload["tenant_id"],
    )

    return user


def require_permission(permission_code: str):
    """Dependency factory for RBAC checks."""

    def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not user.has_permission(permission_code):
            logger.warning(
                "permission_denied",
                permission_code=permission_code,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )

        return user

    return _check


def branch_filter(column: Any, branch_scope: BranchScope) -> Any | None:
    """Build a branch filter, or return None for company-wide access."""
    return None if branch_scope == "all" else column.in_(branch_scope)
```