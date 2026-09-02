import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_tenant_db
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope
from vmss_api.org_structure.deps import authorize_branch_id


def resolve_dashboard_branch_scope(permission_code: str):
    """Query-param counterpart to `org_structure.deps.require_branch_scope`
    (design.md Decision 2): narrows to one branch via `authorize_branch_id`
    when `branchId` is supplied in the query string, otherwise falls back to
    every branch the caller holds `permission_code` at
    (`User.authorized_branch_ids`), rejecting with 403 only if that's empty.

    Reads `branchId` from `Query()` rather than the `X-Branch-ID` header
    every other list endpoint uses — a deliberate, dashboard-only deviation
    (the dashboard page has its own branch-selector control), not a
    parameterization of `require_branch_scope` itself.
    """

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
        tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
        branch_id: Annotated[uuid.UUID | None, Query(alias="branchId")] = None,
    ) -> BranchScope:
        if branch_id is not None:
            branch = await authorize_branch_id(tenant_db, user, permission_code, branch_id)
            return frozenset({branch.id})

        scope = user.authorized_branch_ids(permission_code)
        if scope != "all" and not scope:
            logger.warning("permission_denied", permission_code=permission_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission"
            )
        return scope

    return _check
