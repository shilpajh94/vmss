"""The zone entry decision (add-zone-access-control design.md Decision 4).

`can_enter` is a pure function over facts the service has already loaded: no
I/O, so the whole allow/deny matrix is table-testable. Checks run in a fixed
order and the first failure wins, so an alert names the real cause (a
`blacklisted` visitor is never reported as merely `zone_not_allowed`).
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol


class DenyReason(StrEnum):
    zone_inactive = "zone_inactive"
    gate_not_linked = "gate_not_linked"
    not_checked_in = "not_checked_in"
    not_approved = "not_approved"
    blacklisted = "blacklisted"
    outside_time_window = "outside_time_window"
    zone_not_allowed = "zone_not_allowed"


# `Invitation.status` values that mean the visit has not (or no longer has) an approval.
UNAPPROVED_STATUSES = frozenset({"pending", "submitted", "denied"})


class _Visit(Protocol):
    status: str
    check_in_status: str
    branch_id: uuid.UUID
    expires_at: datetime
    preferred_visit_date: date | None
    watchlist_flagged: bool
    watchlist_override_at: datetime | None


class _Zone(Protocol):
    id: uuid.UUID
    branch_id: uuid.UUID
    is_active: bool
    deleted_at: datetime | None


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: DenyReason | None = None


def _deny(reason: DenyReason) -> AccessDecision:
    return AccessDecision(allowed=False, reason=reason)


def can_enter(
    visit: _Visit,
    zone: _Zone,
    *,
    gate_serves_zone: bool,
    allowed_zone_ids: Collection[uuid.UUID],
    now: datetime,
    local_today: date,
) -> AccessDecision:
    """`now` is an aware instant; `local_today` is the tenant-local date at `now`
    (the caller resolves it with `core/timezones.py`, this module stays clock-free)."""
    if zone.deleted_at is not None or not zone.is_active or zone.branch_id != visit.branch_id:
        return _deny(DenyReason.zone_inactive)
    if not gate_serves_zone:
        return _deny(DenyReason.gate_not_linked)
    if visit.check_in_status != "checked_in" or visit.status in ("checked_out", "archived"):
        return _deny(DenyReason.not_checked_in)
    if visit.status in UNAPPROVED_STATUSES:
        return _deny(DenyReason.not_approved)
    if visit.watchlist_flagged and visit.watchlist_override_at is None:
        return _deny(DenyReason.blacklisted)
    expires_at = (
        visit.expires_at if visit.expires_at.tzinfo else visit.expires_at.replace(tzinfo=UTC)
    )
    if now > expires_at or (
        visit.preferred_visit_date is not None and local_today < visit.preferred_visit_date
    ):
        return _deny(DenyReason.outside_time_window)
    if zone.id not in allowed_zone_ids:
        return _deny(DenyReason.zone_not_allowed)
    return AccessDecision(allowed=True)
