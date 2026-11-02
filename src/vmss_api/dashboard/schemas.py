import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from vmss_api.core.schemas import CamelModel

DashboardCheckInSortableField = Literal["checked_in_at", "checked_out_at"]
DashboardRange = Literal["7d", "30d"]
"""Analytics periods: today plus the preceding 6 or 29 tenant-local days."""
"""Sortable columns for `GET /admin/dashboard/checkins` — same whitelist
posture as `invitations.schemas.InvitationSortableField`
(api-conventions.md §1: never pass a raw client-supplied string into
`order_by()`).
"""


class UpcomingVisitorOut(CamelModel):
    """One row of `DashboardOverviewOut.upcoming_visitors` — an `approved`,
    not-yet-checked-in, non-expired invitation (design.md Decision 6).
    """

    id: uuid.UUID
    tracking_id: str
    primary_contact_full_name: str
    host_id: uuid.UUID | None
    host_full_name: str | None
    purpose_of_visit: str | None
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    expires_at: datetime


class DashboardOverviewOut(CamelModel):
    visits_today_count: int = Field(
        deprecated="Counts invitations created today; use scheduledTodayCount.",
    )
    """Kept unchanged for existing clients until its documented removal date
    (docs/features/dashboard.md; live-dashboards-and-analytics design.md D2).
    """
    scheduled_today_count: int
    scheduled_today_checked_in_count: int
    """`scheduledTodayCount` visits checked in at least once — never more
    than it (fix-dashboard-count-accuracy).
    """
    checked_in_today_count: int
    """Every check-in today, whatever the visit day; equals the sum of the
    hourly arrivals chart.
    """
    checked_in_count: int
    open_pending_approval_count: int
    """`submitted` and not yet expired."""
    oldest_open_pending_submitted_at: datetime | None
    pending_approval_count: int = Field(
        deprecated="Includes expired requests; use openPendingApprovalCount.",
    )
    oldest_pending_submitted_at: datetime | None = Field(
        deprecated="Includes expired requests; use oldestOpenPendingSubmittedAt.",
    )
    upcoming_visitor_count: int
    upcoming_visitors: list[UpcomingVisitorOut]
    today: date
    generated_at: datetime


class MyUpcomingVisitorOut(CamelModel):
    """One row of `MyDashboardOverviewOut.upcoming_preview`."""

    id: uuid.UUID
    tracking_id: str
    primary_contact_full_name: str
    preferred_visit_date: date | None
    preferred_visit_time: time | None
    purpose_of_visit: str | None
    expires_at: datetime


class MyDashboardOverviewOut(CamelModel):
    """`GET /admin/dashboard/my-overview` — counted over the caller's
    `relevantToMe` invitations only.
    """

    visits_today: int
    inside_now: int
    open_awaiting_approval: int
    """`submitted` and not yet expired."""
    awaiting_approval: int = Field(
        deprecated="Includes expired requests; use openAwaitingApproval.",
    )
    upcoming: int
    upcoming_preview: list[MyUpcomingVisitorOut]
    today: date
    generated_at: datetime


class DashboardCheckInListItemOut(CamelModel):
    """One row of `GET /admin/dashboard/checkins`."""

    id: uuid.UUID
    tracking_id: str
    primary_contact_full_name: str
    host_id: uuid.UUID | None
    host_full_name: str | None
    branch_id: uuid.UUID
    status: str
    checked_in_at: datetime | None
    checked_out_at: datetime | None


class DashboardSearchResultOut(CamelModel):
    """One row of `GET /admin/dashboard/search`."""

    id: uuid.UUID
    tracking_id: str
    primary_contact_full_name: str
    status: str
    branch_id: uuid.UUID


class DailyTrendPointOut(CamelModel):
    """One tenant-local day of `dailyTrend` — scheduled visits that day,
    how many were admitted at least once, and how many were archived as
    no-shows.
    """

    date: date
    scheduled: int
    checked_in: int
    no_show: int


class HourlyCheckInsOut(CamelModel):
    hour: int
    count: int


class StatusCountOut(CamelModel):
    status: str
    count: int


class LabelCountOut(CamelModel):
    label: str
    count: int


class MyDashboardAnalyticsOut(CamelModel):
    """`GET /admin/dashboard/my-analytics` — over the caller's
    `relevantToMe` invitations only.
    """

    range: DashboardRange
    timezone: str
    today: date
    generated_at: datetime
    daily_trend: list[DailyTrendPointOut]
    status_breakdown: list[StatusCountOut]


class DashboardAnalyticsOut(MyDashboardAnalyticsOut):
    """`GET /admin/dashboard/analytics` — branch-wide."""

    hourly_check_ins_today: list[HourlyCheckInsOut]
    top_purposes: list[LabelCountOut]
    top_departments: list[LabelCountOut]
