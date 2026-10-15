import uuid
from datetime import date, datetime, time
from typing import Literal

from vmss_api.core.schemas import CamelModel

DashboardCheckInSortableField = Literal["checked_in_at", "checked_out_at"]
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
    purpose_of_visit: str | None
    expires_at: datetime


class DashboardOverviewOut(CamelModel):
    visits_today_count: int
    checked_in_count: int
    pending_approval_count: int
    upcoming_visitor_count: int
    upcoming_visitors: list[UpcomingVisitorOut]


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
    awaiting_approval: int
    upcoming: int
    upcoming_preview: list[MyUpcomingVisitorOut]


class DashboardCheckInListItemOut(CamelModel):
    """One row of `GET /admin/dashboard/checkins`."""

    id: uuid.UUID
    tracking_id: str
    primary_contact_full_name: str
    host_id: uuid.UUID | None
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
