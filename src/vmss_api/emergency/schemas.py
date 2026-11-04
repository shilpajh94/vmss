import uuid
from datetime import datetime

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class InsideVisitorOut(CamelModel):
    """Deliberately name, host and badge number only — no contact or ID details
    (design.md Decision 8)."""

    invitation_id: uuid.UUID
    visitor_name: str
    host_name: str | None
    badge_number: str | None
    entered_at: datetime | None = None


class InsideZoneOut(CamelModel):
    zone_id: uuid.UUID
    zone_name: str
    branch_id: uuid.UUID
    visitors: list[InsideVisitorOut]


class InsideReportOut(CamelModel):
    zones: list[InsideZoneOut]
    unzoned: list[InsideVisitorOut] = Field(
        description="Checked in but not currently inside any zone."
    )
    total_inside: int
