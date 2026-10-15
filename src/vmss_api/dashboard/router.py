from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant, get_tenant_db
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.dashboard import service
from vmss_api.dashboard.deps import resolve_dashboard_branch_scope
from vmss_api.dashboard.schemas import (
    DashboardCheckInListItemOut,
    DashboardCheckInSortableField,
    DashboardOverviewOut,
    DashboardSearchResultOut,
    MyDashboardOverviewOut,
)
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=Envelope[DashboardOverviewOut],
)
async def get_overview(
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view-all"))
    ],
) -> JSONResponse:
    """spec.md "Dashboard Overview Summary" — scoped to `branchId` when
    supplied, otherwise aggregated across every branch the caller holds
    `invitations:view-all` at (design.md Decision 2;
    restrict-delegated-invitation-visibility).
    """
    overview = await service.get_overview(tenant_db, tenant, branch_scope)
    return success_response(data=overview)


@router.get(
    "/my-overview",
    response_model=Envelope[MyDashboardOverviewOut],
)
async def get_my_overview(
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """spec.md "Personal Dashboard Overview Scoped to the Caller's Relevant
    Invitations" — the staff landing page. Any authenticated user; no
    branch-scope dependency, so `X-Branch-ID` is never read. The
    `/admin/dashboard` prefix is historical — the router already serves
    reception and security (staff-lifecycle-emails-and-dashboard-landing
    design.md D6).
    """
    overview = await service.get_my_overview(tenant_db, tenant, user)
    return success_response(data=overview)


@router.get(
    "/checkins",
    response_model=PaginatedEnvelope[DashboardCheckInListItemOut],
)
async def list_checkins(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view-all"))
    ],
    pagination: Annotated[tuple[int, int], Depends(get_pagination)],
    sort_by: Annotated[DashboardCheckInSortableField, Query(alias="sortBy")] = "checked_in_at",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = SortOrder.desc,
) -> JSONResponse:
    """spec.md "Paginated Check-Ins Log" — the dashboard's "View All"
    check-ins list.
    """
    page, page_size = pagination
    items, total = await service.list_checkins_page(
        tenant_db,
        branch_scope,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated_response(data=items, page=page, page_size=page_size, total=total)


@router.get(
    "/search",
    response_model=Envelope[list[DashboardSearchResultOut]],
)
async def search(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view-all"))
    ],
    query: Annotated[str, Query(min_length=2)],
) -> JSONResponse:
    """spec.md "Dashboard Topbar Search" — case-insensitive partial match on
    the primary contact's full name, capped result count.
    """
    results = await service.search_visitors(tenant_db, branch_scope, query=query)
    return success_response(data=results)
