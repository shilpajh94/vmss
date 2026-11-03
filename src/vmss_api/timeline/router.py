import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_pagination, get_tenant_db, require_permission
from vmss_api.core.logging import logger
from vmss_api.core.responses import error_response, paginated_response
from vmss_api.core.schemas import PaginatedEnvelope, SortOrder
from vmss_api.timeline import service
from vmss_api.timeline.schemas import TimelineEventOut, TimelineSortField

# Full paths rather than a prefix: the two routes live under different
# resources (`/invitations`, `/visitors`) but share one feature package.
router = APIRouter(tags=["timeline"])

_NOT_FOUND = "Timeline not found"


@router.get(
    "/invitations/{invitation_id}/timeline",
    response_model=PaginatedEnvelope[TimelineEventOut],
    summary="Chronological history of one visit",
)
async def get_invitation_timeline(
    invitation_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(require_permission("timeline:view"))],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    occurred_after: Annotated[datetime | None, Query(alias="occurredAfter")] = None,
    occurred_before: Annotated[datetime | None, Query(alias="occurredBefore")] = None,
    sort_by: Annotated[TimelineSortField, Query(alias="sortBy")] = TimelineSortField.occurred_at,
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
) -> JSONResponse:
    page, page_size = pagination
    try:
        events, total = await service.get_invitation_timeline(
            tenant_db,
            invitation_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
            page=page,
            page_size=page_size,
            sort_by=sort_by.value,
            sort_order=sort_order,
        )
    except service.TimelineNotFoundError:
        return error_response(_NOT_FOUND, 404)
    logger.info("timeline_viewed", invitation_id=str(invitation_id), result_count=len(events))
    return paginated_response(data=events, page=page, page_size=page_size, total=total)


@router.get(
    "/visitors/{visitor_id}/timeline",
    response_model=PaginatedEnvelope[TimelineEventOut],
    summary="Chronological history of the visit a visitor belongs to",
)
async def get_visitor_timeline(
    visitor_id: uuid.UUID,
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(require_permission("timeline:view"))],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    occurred_after: Annotated[datetime | None, Query(alias="occurredAfter")] = None,
    occurred_before: Annotated[datetime | None, Query(alias="occurredBefore")] = None,
    sort_by: Annotated[TimelineSortField, Query(alias="sortBy")] = TimelineSortField.occurred_at,
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
) -> JSONResponse:
    page, page_size = pagination
    try:
        events, total = await service.get_visitor_timeline(
            tenant_db,
            visitor_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
            page=page,
            page_size=page_size,
            sort_by=sort_by.value,
            sort_order=sort_order,
        )
    except service.TimelineNotFoundError:
        return error_response(_NOT_FOUND, 404)
    logger.info("timeline_viewed", visitor_id=str(visitor_id), result_count=len(events))
    return paginated_response(data=events, page=page, page_size=page_size, total=total)
