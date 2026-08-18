from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.deps import get_tenant_db, require_permission
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import Envelope
from vmss_api.reports import service
from vmss_api.reports.schemas import CrossBranchRollupOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/branches/rollup",
    response_model=Envelope[CrossBranchRollupOut],
    dependencies=[Depends(require_permission("reports:view"))],
)
async def get_branches_rollup(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    """Company-wide, not branch-scoped — the whole point is comparing across
    every branch in one response, same posture as Branch CRUD itself
    (`org_structure/router.py`) rather than `require_branch_permission`.
    """
    rollup = await service.get_cross_branch_rollup(tenant_db)
    return success_response(data=rollup)
