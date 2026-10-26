from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import User
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
from vmss_api.invitations.repository import VisitDayRange
from vmss_api.invitations.service import resolve_visit_timezone
from vmss_api.org_structure.service import get_default_host_role
from vmss_api.tenant.models import Tenant

_UPCOMING_PREVIEW_LIMIT = 10
_SEARCH_RESULT_LIMIT = 10
_MY_UPCOMING_PREVIEW_LIMIT = 5
_TOP_LABEL_LIMIT = 5
_RANGE_DAYS: dict[str, int] = {"7d": 7, "30d": 30}
_NOT_SPECIFIED_LABEL = "Not specified"
_OTHER_LABEL = "Other"


async def _visit_clock(
    tenant_db: AsyncSession, tenant: Tenant, *, now_utc: datetime
) -> tuple[ZoneInfo, date]:
    """The visit timezone (company default, else tenant, else UTC) and
    today's date in it — the zone that decides every invitation's visit
    day and expiry, so "today" here is the day the rest of the system uses
    (fix-dashboard-count-accuracy design.md D1).
    """
    tz = await resolve_visit_timezone(tenant_db, tenant)
    return tz, now_utc.astimezone(tz).date()


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
    tz, today = await _visit_clock(tenant_db, tenant, now_utc=now_utc)
    repository = DashboardRepository(tenant_db)
    counts = await repository.overview_counts(
        branch_scope, today=VisitDayRange.local(today, today, tz), now_utc=now_utc
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
    tz, today = await _visit_clock(tenant_db, tenant, now_utc=now_utc)
    default_host_role_id = (await get_default_host_role(tenant_db)).id
    repository = DashboardRepository(tenant_db)
    counts = await repository.personal_overview_counts(
        user_id=user.id,
        default_host_role_id=default_host_role_id,
        today=VisitDayRange.local(today, today, tz),
        now_utc=now_utc,
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
    tz: ZoneInfo,
    today: date,
    range_: DashboardRange,
    now_utc: datetime,
) -> dict[str, Any]:
    timezone = tz.key
    start, end = _range_bounds(today, range_)
    days = VisitDayRange.local(start, end, tz)
    trend_rows = await repository.daily_trend(scope_clause, days=days, timezone=timezone)
    status_rows = await repository.status_breakdown(scope_clause, days=days)
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
    tz, today = await _visit_clock(tenant_db, tenant, now_utc=now_utc)
    repository = DashboardRepository(tenant_db)
    scope_clause = repository.branch_scope_clause(branch_scope)
    common = await _common_analytics(
        repository, scope_clause, tz=tz, today=today, range_=range_, now_utc=now_utc
    )
    start, end = _range_bounds(today, range_)
    days = VisitDayRange.local(start, end, tz)
    hourly = dict(
        await repository.hourly_check_ins(
            scope_clause, timezone=common["timezone"], today=VisitDayRange.local(today, today, tz)
        )
    )
    return DashboardAnalyticsOut(
        **common,
        hourly_check_ins_today=[
            HourlyCheckInsOut(hour=hour, count=hourly.get(hour, 0)) for hour in range(24)
        ],
        top_purposes=_top_labels(await repository.top_purposes(scope_clause, days=days)),
        top_departments=_top_labels(await repository.top_departments(scope_clause, days=days)),
    )


async def get_my_analytics(
    tenant_db: AsyncSession, tenant: Tenant, user: User, *, range_: DashboardRange
) -> MyDashboardAnalyticsOut:
    """Same relevance rule as `get_my_overview` — no branch scope."""
    now_utc = datetime.now(UTC)
    tz, today = await _visit_clock(tenant_db, tenant, now_utc=now_utc)
    default_host_role_id = (await get_default_host_role(tenant_db)).id
    repository = DashboardRepository(tenant_db)
    scope_clause = repository.personal_scope_clause(user.id, default_host_role_id)
    common = await _common_analytics(
        repository, scope_clause, tz=tz, today=today, range_=range_, now_utc=now_utc
    )
    return MyDashboardAnalyticsOut(**common)
