from datetime import datetime
from enum import StrEnum

from vmss_api.core.schemas import CamelModel


class TimelineEventType(StrEnum):
    invited = "invited"
    approved = "approved"
    denied = "denied"
    approval_reverted = "approval_reverted"
    id_verified = "id_verified"
    photo_captured = "photo_captured"
    checked_in = "checked_in"
    checked_out = "checked_out"
    badge_printed = "badge_printed"
    badge_reprinted = "badge_reprinted"
    notification_sent = "notification_sent"
    zone_entered = "zone_entered"
    zone_exited = "zone_exited"
    zone_entry_denied = "zone_entry_denied"


class TimelineSortField(StrEnum):
    occurred_at = "occurred_at"
    event_type = "event_type"


class TimelineEventOut(CamelModel):
    """Deliberately has no `diff`, token or storage-key field — nothing
    sensitive can leak through this shape."""

    event_type: TimelineEventType
    occurred_at: datetime
    summary: str
    actor_name: str | None = None
