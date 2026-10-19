from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
from vmss_api.core.logging import logger
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.dashboard.repository import BREAKDOWN_STATUSES, DashboardRepository
from vmss_api.dashboard.schemas import (
    DailyTrendPointOut,
    DashboardAnalyticsOut,
    DashboardCheckInListItemOut,
    DashboardOverviewOut,
    DashboardRange,
    DashboardSearchResultOut,
    HourlyCheckInsOut,
    LabelCountOut,
    MyDashboardAnalyticsOut,
    MyDashboardOverviewOut,
    MyUpcomingVisitorOut,
    StatusCountOut,
    UpcomingVisitorOut,
)
from vmss_api.invitations.models import Invitation
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant

_UPCOMING_PREVIEW_LIMIT = 10
_SEARCH_RESULT_LIMIT = 10
_MY_UPCOMING_PREVIEW_LIMIT = 5
_TOP_LABEL_LIMIT = 5
_RANGE_DAYS: dict[str, int] = {"7d": 7, "30d": 30}
_NOT_SPECIFIED_LABEL = "Not specified"
_OTHER_LABEL = "Other"


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


def _local_today(tenant: Tenant, *, now_utc: datetime) -> date:
    return now_utc.astimezone(_resolve_tenant_timezone(tenant)).date()


def _to_upcoming_visitor_out(
    invitation: Invitation, host_full_name: str | None
) -> UpcomingVisitorOut:
    return UpcomingVisitorOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        host_id=invitation.host_id,
        host_full_name=host_full_name,
        purpose_of_visit=invitation.purpose_of_visit,
        preferred_visit_date=invitation.preferred_visit_date,
        preferred_visit_time=invitation.preferred_visit_time,
        expires_at=invitation.expires_at,
    )


def _to_checkin_list_item_out(
    invitation: Invitation, host_full_name: str | None
) -> DashboardCheckInListItemOut:
    return DashboardCheckInListItemOut(
        id=invitation.id,
        tracking_id=invitation.tracking_id,
        primary_contact_full_name=invitation.primary_contact_full_name,
        host_id=invitation.host_id,
        host_full_name=host_full_name,
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
    today = _local_today(tenant, now_utc=now_utc)
    repository = DashboardRepository(tenant_db)
    counts = await repository.overview_counts(
        branch_scope,
        today=today,
        day_start_utc=day_start_utc,
        day_end_utc=day_end_utc,
        now_utc=now_utc,
    )
    upcoming = await repository.upcoming_visitors_preview(
        branch_scope, now_utc=now_utc, limit=_UPCOMING_PREVIEW_LIMIT
    )
    return DashboardOverviewOut(
        upcoming_visitors=[
            _to_upcoming_visitor_out(invitation, host_name) for invitation, host_name in upcoming
        ],
        today=today,
        generated_at=now_utc,
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
    today = _local_today(tenant, now_utc=now_utc)
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
        today=today,
        generated_at=now_utc,
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
    return [_to_checkin_list_item_out(row, host_name) for row, host_name in rows], total


async def search_visitors(
    tenant_db: AsyncSession, branch_scope: BranchScope, *, query: str
) -> list[DashboardSearchResultOut]:
    rows = await DashboardRepository(tenant_db).search_by_contact_name(
        branch_scope, query=query, limit=_SEARCH_RESULT_LIMIT
    )
    return [_to_search_result_out(row) for row in rows]


# --- Analytics (live-dashboards-and-analytics design.md D3) ----------------


def _range_bounds(today: date, range_: DashboardRange) -> tuple[date, date]:
    return today - timedelta(days=_RANGE_DAYS[range_] - 1), today


def _zero_filled_trend(
    rows: list[tuple[date, int, int, int]], *, start: date, end: date
) -> list[DailyTrendPointOut]:
    by_day = {row[0]: row for row in rows}
    points: list[DailyTrendPointOut] = []
    day = start
    while day <= end:
        _, scheduled, checked_in, no_show = by_day.get(day, (day, 0, 0, 0))
        points.append(
            DailyTrendPointOut(
                date=day, scheduled=scheduled, checked_in=checked_in, no_show=no_show
            )
        )
        day += timedelta(days=1)
    return points


def _zero_filled_statuses(rows: list[tuple[str, int]]) -> list[StatusCountOut]:
    counts = dict(rows)
    return [
        StatusCountOut(status=status, count=counts.get(status, 0)) for status in BREAKDOWN_STATUSES
    ]


def _top_labels(rows: list[tuple[str | None, int]]) -> list[LabelCountOut]:
    """Top 5 by count (ties alphabetical), the rest summed into one "Other"
    row shown only when non-zero. NULL labels merge into "Not specified".
    """
    merged: dict[str, int] = {}
    for label, count in rows:
        key = label or _NOT_SPECIFIED_LABEL
        merged[key] = merged.get(key, 0) + count
    ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0].lower()))
    top = [LabelCountOut(label=label, count=count) for label, count in ranked[:_TOP_LABEL_LIMIT]]
    remainder = sum(count for _, count in ranked[_TOP_LABEL_LIMIT:])
    if remainder > 0:
        top.append(LabelCountOut(label=_OTHER_LABEL, count=remainder))
    return top


async def _common_analytics(
    repository: DashboardRepository,
    scope_clause: Any | None,
    *,
    tenant: Tenant,
    range_: DashboardRange,
    now_utc: datetime,
) -> dict[str, Any]:
    timezone = _resolve_tenant_timezone(tenant).key
    today = _local_today(tenant, now_utc=now_utc)
    start, end = _range_bounds(today, range_)
    trend_rows = await repository.daily_trend(scope_clause, start=start, end=end)
    status_rows = await repository.status_breakdown(
        scope_clause, timezone=timezone, start=start, end=end
    )
    return {
        "range": range_,
        "timezone": timezone,
        "today": today,
        "generated_at": now_utc,
        "daily_trend": _zero_filled_trend(trend_rows, start=start, end=end),
        "status_breakdown": _zero_filled_statuses(status_rows),
    }


async def get_analytics(
    tenant_db: AsyncSession, tenant: Tenant, branch_scope: BranchScope, *, range_: DashboardRange
) -> DashboardAnalyticsOut:
    now_utc = datetime.now(UTC)
    repository = DashboardRepository(tenant_db)
    scope_clause = repository.branch_scope_clause(branch_scope)
    common = await _common_analytics(
        repository, scope_clause, tenant=tenant, range_=range_, now_utc=now_utc
    )
    start, end = _range_bounds(common["today"], range_)
    day_start_utc, day_end_utc = _today_bounds_utc(tenant, now_utc=now_utc)
    hourly = dict(
        await repository.hourly_check_ins(
            scope_clause,
            timezone=common["timezone"],
            day_start_utc=day_start_utc,
            day_end_utc=day_end_utc,
        )
    )
    return DashboardAnalyticsOut(
        **common,
        hourly_check_ins_today=[
            HourlyCheckInsOut(hour=hour, count=hourly.get(hour, 0)) for hour in range(24)
        ],
        top_purposes=_top_labels(await repository.top_purposes(scope_clause, start=start, end=end)),
        top_departments=_top_labels(
            await repository.top_departments(scope_clause, start=start, end=end)
        ),
    )


async def get_my_analytics(
    tenant_db: AsyncSession, tenant: Tenant, user: User, *, range_: DashboardRange
) -> MyDashboardAnalyticsOut:
    """Same relevance rule as `get_my_overview` — no branch scope."""
    now_utc = datetime.now(UTC)
    default_host_role_id = (await get_default_host_role(tenant_db)).id
    repository = DashboardRepository(tenant_db)
    scope_clause = repository.personal_scope_clause(user.id, default_host_role_id)
    common = await _common_analytics(
        repository, scope_clause, tenant=tenant, range_=range_, now_utc=now_utc
    )
    return MyDashboardAnalyticsOut(**common)
