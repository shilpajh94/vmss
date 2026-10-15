from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.dashboard.repository import DashboardRepository
from vmss_api.dashboard.schemas import (
    DashboardCheckInListItemOut,
    DashboardOverviewOut,
    DashboardSearchResultOut,
    MyDashboardOverviewOut,
    MyUpcomingVisitorOut,
    UpcomingVisitorOut,
)
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant

_UPCOMING_PREVIEW_LIMIT = 10
_SEARCH_RESULT_LIMIT = 10
_MY_UPCOMING_PREVIEW_LIMIT = 5


def _resolve_tenant_timezone(tenant: Tenant) -> ZoneInfo:
    """`Tenant.timezone` is a free-text column with no DB-level `CHECK`
    constraint (database-architecture.md §4 doesn't require one, and this
    is the first feature to interpret it as a real IANA zone name) — falls
    back to UTC rather than a 500 if it doesn't resolve, logging a
    `WARNING` per logging-observability.md §3's "recoverable anomaly".
    """
    try:
        return ZoneInfo(tenant.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("dashboard_invalid_tenant_timezone", tenant_timezone=tenant.timezone)
        return ZoneInfo("UTC")


def _today_bounds_utc(tenant: Tenant, *, now_utc: datetime) -> tuple[datetime, datetime]:
    """ "Today" per the tenant's own configured timezone (design.md
    Decision 5), converted back to a plain UTC range so the repository's
    query stays one indexed `created_at` range scan rather than a per-row
    Python filter.
    """
    tz = _resolve_tenant_timezone(tenant)
    local_day_start = now_utc.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = local_day_start.astimezone(UTC)
    day_end_utc = (local_day_start + timedelta(days=1)).astimezone(UTC)
    return day_start_utc, day_end_utc


def _to_upcoming_visitor_out(invitation: Invitation) -> UpcomingVisitorOut:
    return UpcomingVisitorOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        host_id=invitation.host_id,
        purpose_of_visit=invitation.purpose_of_visit,
        expires_at=invitation.expires_at,
    )


def _to_checkin_list_item_out(invitation: Invitation) -> DashboardCheckInListItemOut:
    return DashboardCheckInListItemOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        host_id=invitation.host_id,
        branch_id=invitation.branch_id,
        status=invitation.status,
        checked_in_at=invitation.checked_in_at,
        checked_out_at=invitation.checked_out_at,
    )


def _to_search_result_out(invitation: Invitation) -> DashboardSearchResultOut:
    return DashboardSearchResultOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        status=invitation.status,
        branch_id=invitation.branch_id,
    )


async def get_overview(
    tenant_db: AsyncSession, tenant: Tenant, branch_scope: BranchScope
) -> DashboardOverviewOut:
    now_utc = datetime.now(UTC)
    day_start_utc, day_end_utc = _today_bounds_utc(tenant, now_utc=now_utc)
    repository = DashboardRepository(tenant_db)
    counts = await repository.overview_counts(
        branch_scope, day_start_utc=day_start_utc, day_end_utc=day_end_utc, now_utc=now_utc
    )
    upcoming = await repository.upcoming_visitors_preview(
        branch_scope, now_utc=now_utc, limit=_UPCOMING_PREVIEW_LIMIT
    )
    return DashboardOverviewOut(
        upcoming_visitors=[_to_upcoming_visitor_out(invitation) for invitation in upcoming],
        **counts,
    )


async def get_my_overview(
    tenant_db: AsyncSession, tenant: Tenant, user: User
) -> MyDashboardOverviewOut:
    """No branch scope at all — the `relevantToMe` predicate is the whole
    authorization, same as `GET /invitations?relevantToMe=true` (design.md
    D6). The default host role is resolved here exactly as that list does.
    """
    now_utc = datetime.now(UTC)
    day_start_utc, _ = _today_bounds_utc(tenant, now_utc=now_utc)
    today = day_start_utc.astimezone(_resolve_tenant_timezone(tenant)).date()
    default_host_role_id = (await get_default_host_role(tenant_db)).id
    repository = DashboardRepository(tenant_db)
    counts = await repository.personal_overview_counts(
        user_id=user.id, default_host_role_id=default_host_role_id, today=today, now_utc=now_utc
    )
    upcoming = await repository.personal_upcoming_preview(
        user_id=user.id,
        default_host_role_id=default_host_role_id,
        now_utc=now_utc,
        limit=_MY_UPCOMING_PREVIEW_LIMIT,
    )
    return MyDashboardOverviewOut(
        upcoming_preview=[MyUpcomingVisitorOut.model_validate(row) for row in upcoming],
        **counts,
    )


async def list_checkins_page(
    tenant_db: AsyncSession,
    branch_scope: BranchScope,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
) -> tuple[list[DashboardCheckInListItemOut], int]:
    rows, total = await DashboardRepository(tenant_db).paginated_checkins(
        branch_scope, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return [_to_checkin_list_item_out(row) for row in rows], total


async def search_visitors(
    tenant_db: AsyncSession, branch_scope: BranchScope, *, query: str
) -> list[DashboardSearchResultOut]:
    rows = await DashboardRepository(tenant_db).search_by_contact_name(
        branch_scope, query=query, limit=_SEARCH_RESULT_LIMIT
    )
    return [_to_search_result_out(row) for row in rows]
