from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.access_control.deps import require_zone_access_enabled
from vmss_api.core.deps import get_tenant_db
from vmss_api.core.logging import logger
from vmss_api.core.responses import success_response
from vmss_api.core.schemas import BranchScope, Envelope
from vmss_api.emergency import service
from vmss_api.emergency.schemas import InsideReportOut
from vmss_api.org_structure.deps import require_branch_scope

router = APIRouter(
    prefix="/emergency",
    tags=["emergency"],
    dependencies=[Depends(require_zone_access_enabled)],
)


@router.get(
    "/inside",
    response_model=Envelope[InsideReportOut],
    summary="Who is inside right now, grouped by zone",
)
async def get_inside(
    branch_scope: Annotated[BranchScope, Depends(require_branch_scope("emergency:view"))],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> JSONResponse:
    report = await service.inside_report(tenant_db, branch_scope)
    logger.info("emergency_inside_viewed", total_inside=report.total_inside)
    return success_response(data=report)
