import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.config import settings
from vmss_api.core.database import get_db, tenant_session_scope
from vmss_api.core.deps import get_current_user, get_tenant_db
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope
from vmss_api.core.security import decode_token
from vmss_api.org_structure.models import Branch
from vmss_api.org_structure.repository import BranchRepository
from vmss_api.tenant.models import Tenant
from vmss_api.tenant.repository import TenantRepository

_optional_bearer_scheme = HTTPBearer(auto_error=False)


def _authorize_branch(
    branch: Branch | None, user: User, permission_code: str | None = None
) -> Branch:
    """Shared not-found/inactive, branch-access, and (when given a
    `permission_code`) permission checks behind `get_branch_context`,
    `authorize_branch_id`, and `authorize_branch_id_tolerant`. The three
    differ only in how `branch` itself gets fetched before being handed
    here — `BranchRepository.get` vs `.get_including_deleted`, or resolved
    from an `X-Branch-ID` header rather than a body-supplied id — and in
    whether a permission check applies at all: `get_branch_context` resolves
    branch *context* only (the permission check happens separately, once a
    route knows which permission it needs, via `require_branch_permission`),
    so it calls this with no `permission_code` and that check is skipped,
    exactly as before this extraction.
    """
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    if not user.has_branch_access(branch.id):
        logger.warning("branch_access_denied", branch_id=str(branch.id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch"
        )
    if permission_code is not None and not user.has_permission(
        permission_code, branch_id=branch.id
    ):
        logger.warning(
            "permission_denied", permission_code=permission_code, branch_id=str(branch.id)
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
    structlog.contextvars.bind_contextvars(branch_id=str(branch.id))
    return branch


async def get_branch_context(
    x_branch_id: Annotated[uuid.UUID, Header(alias="X-Branch-ID")],
    user: Annotated[User, Depends(get_current_user)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Branch:
    """Resolves and authorizes the branch a request operates against, from
    the `X-Branch-ID` header rather than a JWT claim: a user who works across
    branches in one login session (a roaming Security guard, an Admin)
    switches branch per request instead of re-authenticating. See
    `auth/models.py::User.has_branch_access`.
    """
    branch = await BranchRepository(tenant_db).get(x_branch_id)
    return _authorize_branch(branch, user)


def require_branch_permission(permission_code: str):
    """Branch-scoped counterpart to `core.deps.require_permission` — grants
    if the caller has `permission_code` either company-wide (a branch-less
    role assignment) or specifically at the resolved branch.

    `X-Branch-ID` is required here (unlike `require_branch_scope` below).
    `POST /invitations` no longer uses this dependency — its payload now
    carries its own `branchId` fallback, resolved via `authorize_branch_id`
    directly in `invitations/router.py`.
    """

    def _check(
        branch: Annotated[Branch, Depends(get_branch_context)],
        user: Annotated[User, Depends(get_current_user)],
    ) -> Branch:
        if not user.has_permission(permission_code, branch_id=branch.id):
            logger.warning(
                "permission_denied", permission_code=permission_code, branch_id=str(branch.id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
            )
        return branch

    return _check


async def authorize_branch_id(
    tenant_db: AsyncSession, user: User, permission_code: str, branch_id: uuid.UUID
) -> Branch:
    """Same checks as `get_branch_context`/`require_branch_permission`, but
    for a branch id already known from a request body (`branchId` directly,
    or resolved transitively via `buildingId`/`floorId`) rather than a
    header — used by creation endpoints, which no longer require
    `X-Branch-ID` at all (design.md Decision 2).
    """
    branch = await BranchRepository(tenant_db).get(branch_id)
    return _authorize_branch(branch, user, permission_code)


async def authorize_branch_id_tolerant(
    tenant_db: AsyncSession, user: User, permission_code: str, branch_id: uuid.UUID
) -> Branch:
    """Same checks as `authorize_branch_id`, but tolerates the branch itself
    having been soft-deleted — for authorizing an action against an
    *existing* record's own recorded `branch_id` (e.g. approving an
    invitation whose branch was later soft-deleted), where the id is
    already-persisted data, not something the caller supplied and could use
    to probe an unrelated branch. Never use this for create-time validation,
    where a soft-deleted branch must still be treated as absent — see
    `authorize_branch_id`.
    """
    branch = await BranchRepository(tenant_db).get_including_deleted(branch_id)
    return _authorize_branch(branch, user, permission_code)


def require_branch_scope(permission_code: str):
    """List-endpoint counterpart to `require_branch_permission` with an
    optional `X-Branch-ID`: narrows to that one branch when it's supplied
    (identical 404/403 checks to today), otherwise falls back to every
    branch the caller holds `permission_code` at
    (`auth/models.py::User.authorized_branch_ids`), rejecting with 403 only
    if that's empty (design.md Decision 2).
    """

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
        tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
        x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
    ) -> BranchScope:
        if x_branch_id is not None:
            branch = await authorize_branch_id(tenant_db, user, permission_code, x_branch_id)
            return frozenset({branch.id})

        scope = user.authorized_branch_ids(permission_code)
        if scope != "all" and not scope:
            logger.warning("permission_denied", permission_code=permission_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
            )
        return scope

    return _check


async def _tenant_from_bearer_token(
    db: AsyncSession, credentials: HTTPAuthorizationCredentials
) -> Tenant | None:
    """Best-effort tenant resolution from an optionally-presented token —
    never raises: an absent, malformed, expired, or otherwise unusable
    token simply yields `None` so the caller falls back to the default
    tenant, per spec.md's "An expired or invalid token no longer blocks
    listing".
    """
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
    """Tenant resolution for org-structure's public listing endpoints.

    Prefers the caller's own tenant when a valid access token is presented
    — so an authenticated multi-tenant caller lists their own org-structure
    data, not the deployment's default tenant (`test_staff_admin_full_workflow`
    is exactly this case: an admin of a freshly-provisioned, non-default
    tenant listing its own branches). Falls back to
    `settings.default_tenant_slug` — mirroring
    `invitations/deps.py::track_default_tenant_db` and
    `identity_verification/deps.py::default_tenant_id`'s same known
    single-tenant limitation — when no token is presented, or it doesn't
    resolve to a real, active tenant.
    """
    tenant = await _tenant_from_bearer_token(db, credentials) if credentials is not None else None
    if tenant is None:
        tenant = await TenantRepository(db).get_by_slug(settings.default_tenant_slug)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    async with tenant_session_scope(tenant.schema_name) as session:
        yield session


async def public_branch_scope(
    tenant_db: Annotated[AsyncSession, Depends(public_tenant_db)],
    x_branch_id: Annotated[uuid.UUID | None, Header(alias="X-Branch-ID")] = None,
) -> BranchScope:
    """Public counterpart to `require_branch_scope` — no caller, so no
    permission check: `X-Branch-ID` narrows to that one branch when
    supplied, otherwise every branch in the tenant is in scope.
    """
    if x_branch_id is not None:
        branch = await BranchRepository(tenant_db).get(x_branch_id)
        if branch is None or not branch.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        return frozenset({branch.id})
    return "all"
