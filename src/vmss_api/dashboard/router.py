import json
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.audit import record_audit_log
from vmss_api.auth.models import User
from vmss_api.core.deps import get_current_user, get_pagination, get_tenant, get_tenant_db
from vmss_api.core.redis import get_redis
from vmss_api.core.responses import paginated_response, success_response
from vmss_api.core.schemas import BranchScope, Envelope, PaginatedEnvelope, SortOrder
from vmss_api.dashboard import service
from vmss_api.dashboard.deps import resolve_dashboard_branch_scope
from vmss_api.dashboard.schemas import (
    DashboardCheckInListItemOut,
    DashboardCheckInRequest,
    DashboardCheckInSortableField,
    DashboardOverviewOut,
    DashboardSearchResultOut,
)
from vmss_api.invitations.router import to_invitation_out
from vmss_api.invitations.schemas import InvitationOut
from vmss_api.tenant.models import Tenant

router = APIRouter(prefix="/admin/dashboard", tags=["dashboard"])

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


def _idempotency_cache_key(tenant_id: uuid.UUID, idempotency_key: str) -> str:
    return f"vmss:{tenant_id}:dashboard:idempotency:{idempotency_key}"


async def _cached_response(
    tenant_id: uuid.UUID, idempotency_key: str | None
) -> JSONResponse | None:
    """api-conventions.md §3 — a retried check-in request with the same
    `Idempotency-Key` returns the original response instead of checking the
    visitor in twice. Same Redis convention as
    `invitations/router.py::_cached_response`, duplicated rather than shared
    (design.md Decision 4 — not extracted speculatively).
    """
    if idempotency_key is None:
        return None
    redis = await get_redis()
    cached = await redis.get(_idempotency_cache_key(tenant_id, idempotency_key))
    if cached is None:
        return None
    payload = json.loads(cached)
    return JSONResponse(content=payload["body"], status_code=payload["status"])


async def _cache_response(
    tenant_id: uuid.UUID, idempotency_key: str | None, response: JSONResponse
) -> None:
    if idempotency_key is None:
        return
    redis = await get_redis()
    await redis.set(
        _idempotency_cache_key(tenant_id, idempotency_key),
        json.dumps({"status": response.status_code, "body": json.loads(bytes(response.body))}),
        ex=_IDEMPOTENCY_TTL_SECONDS,
    )


@router.get(
    "/overview",
    response_model=Envelope[DashboardOverviewOut],
)
async def get_overview(
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view"))
    ],
) -> JSONResponse:
    """spec.md "Dashboard Overview Summary" — scoped to `branchId` when
    supplied, otherwise aggregated across every branch the caller holds
    `invitations:view` at (design.md Decision 2).
    """
    overview = await service.get_overview(tenant_db, tenant, branch_scope)
    return success_response(data=overview)


@router.patch(
    "/upcoming-visitors",
    response_model=Envelope[InvitationOut],
)
async def check_in_upcoming_visitor(
    payload: DashboardCheckInRequest,
    background_tasks: BackgroundTasks,
    tenant: Annotated[Tenant, Depends(get_tenant)],
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional. Omitting it simply forgoes retry-dedup safety — a "
                "retried request with no key may check in twice. See "
                "api-conventions.md §3."
            ),
        ),
    ] = None,
) -> JSONResponse:
    """spec.md "Check In an Upcoming Visitor From the Dashboard" — the
    dashboard's "upcoming visitors" widget triggers this by row
    (`invitationId` in the body), calling the same
    `invitations.service.check_in_invitation` business rule as
    `PATCH /invitations/{id}/check-in` (design.md Decision 4).
    """
    cached = await _cached_response(tenant.id, idempotency_key)
    if cached is not None:
        return cached

    invitation = await service.check_in_upcoming_visitor(
        tenant_db, payload.invitation_id, user=user, tenant=tenant
    )
    background_tasks.add_task(
        record_audit_log,
        tenant.schema_name,
        actor_user_id=user.id,
        action="invitation_checked_in",
        entity_type="Invitation",
        entity_id=invitation.id,
    )
    response = success_response(data=to_invitation_out(invitation))
    await _cache_response(tenant.id, idempotency_key, response)
    return response


@router.get(
    "/checkins",
    response_model=PaginatedEnvelope[DashboardCheckInListItemOut],
)
async def list_checkins(
    tenant_db: Annotated[AsyncSession, Depends(get_tenant_db)],
    branch_scope: Annotated[
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view"))
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
        BranchScope, Depends(resolve_dashboard_branch_scope("invitations:view"))
    ],
    query: Annotated[str, Query(min_length=2)],
) -> JSONResponse:
    """spec.md "Dashboard Topbar Search" — case-insensitive partial match on
    the primary contact's full name, capped result count.
    """
    results = await service.search_visitors(tenant_db, branch_scope, query=query)
    return success_response(data=results)
