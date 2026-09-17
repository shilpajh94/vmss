"""Branch/tenant-default scope resolution for `form_builder`'s admin
endpoints (`X-Branch-ID` optional: present -> that branch's scope, absent ->
the tenant-wide default, `branch_id=None`), plus a public tenant-resolution
dependency for the not-permission-gated effective-form read
(specs/form-builder/spec.md "Form Builder Access Is Permission-Gated" makes
that resolution explicit).

`public_tenant_db` is a deliberate per-feature copy, not an import from
`visitors`/`org_structure` — see `visitors/deps.py`'s own docstring for why
each public-endpoint feature keeps its own.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.deps import get_current_user, get_tenant_db
from vmss_api.core.logging import logger
from vmss_api.core.security import decode_token
from vmss_api.org_structure.repository import BranchRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_optional_bearer_scheme = HTTPBearer(auto_error=False)


def require_form_scope(permission_code: str):
    """Resolves the caller's target scope from an optional `X-Branch-ID`
    header and checks `permission_code` against it: a company-wide grant
    is required for the tenant-default scope (no header), a company-wide or
    that-branch grant for a specific branch (header present).
    """

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
        tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
        x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
    ) -> uuid.UUID | None:
        if x_branch_id is None:
            if not user.has_permission(permission_code, branch_id=None):
                logger.warning(
                    "permission_denied", permission_code=permission_code, scope="default"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
                )
            return None
        branch = await BranchRepository(tenant_db).get(x_branch_id)
        if branch is None or not branch.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        if not user.has_branch_access(branch.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch"
            )
        if not user.has_permission(permission_code, branch_id=branch.id):
            logger.warning(
                "permission_denied", permission_code=permission_code, branch_id=str(branch.id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
            )
        return branch.id

    return _check


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
        tenant_id = uuid.UUID(raw_tenant_id)
    except ValueError:
        return None
    return await TenantRepository(db).get(tenant_id)


async def public_tenant_db(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer_scheme)
    ] = None,
) -> AsyncGenerator[AsyncSession]:
    tenant = await _tenant_from_bearer_token(db, credentials) if credentials is not None else None
    if tenant is None:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session


async def public_tenant(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer_scheme)
    ] = None,
) -> Tenant:
    tenant = await _tenant_from_bearer_token(db, credentials) if credentials is not None else None
    if tenant is None:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    return tenant


async def public_optional_branch_id(
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
) -> uuid.UUID | None:
    """No caller, so no permission check — just resolves and validates the
    optional branch the public visitor-facing form is being rendered for.
    """
    if x_branch_id is None:
        return None
    branch = await BranchRepository(tenant_db).get(x_branch_id)
    if branch is None or not branch.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch.id
