import uuid
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_tenant_db
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope
from vmss_api.org_structure.models import Branch
from vmss_api.org_structure.repository import BranchRepository


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
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    if not user.has_branch_access(branch.id):
        logger.warning("branch_access_denied", branch_id=str(branch.id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch"
        )
    structlog.contextvars.bind_contextvars(branch_id=str(branch.id))
    return branch


def require_branch_permission(permission_code: str):
    """Branch-scoped counterpart to `core.deps.require_permission` — grants
    if the caller has `permission_code` either company-wide (a branch-less
    role assignment) or specifically at the resolved branch.

    `X-Branch-ID` is required here (unlike `require_branch_scope` below) —
    kept verbatim for `POST /invitations`, the one endpoint whose payload
    carries no branch-identifying field of its own to fall back on.
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
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    if not user.has_branch_access(branch.id):
        logger.warning("branch_access_denied", branch_id=str(branch.id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No access to this branch"
        )
    if not user.has_permission(permission_code, branch_id=branch.id):
        logger.warning(
            "permission_denied", permission_code=permission_code, branch_id=str(branch.id)
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
    structlog.contextvars.bind_contextvars(branch_id=str(branch.id))
    return branch


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
