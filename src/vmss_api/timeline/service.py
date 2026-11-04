import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.masking import mask_text
from vmss_api.core.schemas import SortOrder
from vmss_api.timeline.repository import TimelineRepository, TimelineRow
from vmss_api.timeline.schemas import TimelineEventOut, TimelineEventType


class TimelineNotFoundError(Exception):
    pass


_SUMMARIES: dict[TimelineEventType, str] = {
    TimelineEventType.invited: "Visit invited",
    TimelineEventType.approved: "Visit approved",
    TimelineEventType.denied: "Visit denied",
    TimelineEventType.approval_reverted: "Approval reverted",
    TimelineEventType.id_verified: "ID verified",
    TimelineEventType.photo_captured: "Photo captured",
    TimelineEventType.checked_in: "Checked in",
    TimelineEventType.checked_out: "Checked out",
    TimelineEventType.badge_printed: "Badge printed",
}


_DENY_LABELS = {
    "zone_inactive": "zone unavailable",
    "gate_not_linked": "wrong gate for this zone",
    "not_checked_in": "visitor not checked in",
    "not_approved": "visit not approved",
    "blacklisted": "visitor flagged",
    "outside_time_window": "outside the visit window",
    "zone_not_allowed": "zone not permitted for this visitor",
}


def _denied_summary(detail: str | None) -> str:
    """`detail` is "<zone name> (<reason code>)"; show a label, not the raw code."""
    if not detail:
        return "Zone entry denied"
    name, _, tail = detail.rpartition(" (")
    reason = _DENY_LABELS.get(tail.removesuffix(")"))
    if not name or reason is None:
        return f"Zone entry denied: {mask_text(detail)}"
    return f"Zone entry denied: {mask_text(name)} ({reason})"


def _summary(event_type: TimelineEventType, detail: str | None) -> str:
    if event_type == TimelineEventType.badge_reprinted:
        return f"Badge reprinted: {mask_text(detail)}" if detail else "Badge reprinted"
    if event_type == TimelineEventType.zone_entered:
        return f"Entered zone: {mask_text(detail)}" if detail else "Entered zone"
    if event_type == TimelineEventType.zone_exited:
        return f"Left zone: {mask_text(detail)}" if detail else "Left zone"
    if event_type == TimelineEventType.zone_entry_denied:
        return _denied_summary(detail)
    if event_type == TimelineEventType.notification_sent:
        return f"Notification sent: {mask_text(detail)}" if detail else "Notification sent"
    return _SUMMARIES[event_type]


def _to_event(row: TimelineRow, names: dict[uuid.UUID, str]) -> TimelineEventOut:
    event_type = TimelineEventType(row.event_type)
    return TimelineEventOut(
        event_type=event_type,
        occurred_at=row.occurred_at,
        summary=_summary(event_type, row.detail),
        actor_name=names.get(row.actor_user_id) if row.actor_user_id else None,
    )


async def get_invitation_timeline(
    session: AsyncSession,
    invitation_id: uuid.UUID,
    *,
    occurred_after: datetime | None,
    occurred_before: datetime | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
    include_zones: bool = False,
) -> tuple[list[TimelineEventOut], int]:
    repository = TimelineRepository(session)
    if not await repository.invitation_exists(invitation_id):
        raise TimelineNotFoundError
    rows, total = await repository.list_page(
        invitation_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_zones=include_zones,
    )
    names = await repository.actor_names({r.actor_user_id for r in rows if r.actor_user_id})
    return [_to_event(row, names) for row in rows], total


async def get_visitor_timeline(
    session: AsyncSession,
    visitor_id: uuid.UUID,
    *,
    occurred_after: datetime | None,
    occurred_before: datetime | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: SortOrder,
    include_zones: bool = False,
) -> tuple[list[TimelineEventOut], int]:
    invitation_id = await TimelineRepository(session).invitation_id_for_visitor(visitor_id)
    if invitation_id is None:
        raise TimelineNotFoundError
    return await get_invitation_timeline(
        session,
        invitation_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_zones=include_zones,
    )
