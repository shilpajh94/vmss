import uuid
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import Select, case, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.auth.models import AuditLog, User
from vmss_api.checkin.models import BadgePrint
from vmss_api.core.database import order_clause
from vmss_api.core.schemas import SortOrder
from vmss_api.invitations.models import Invitation, InvitationVisitor
from vmss_api.notifications.models import Notification
from vmss_api.timeline.mapping import AUDIT_ACTION_TO_EVENT, INVITATION_ENTITY_TYPES
from vmss_api.timeline.schemas import TimelineEventType


class TimelineRow(NamedTuple):
    occurred_at: datetime
    event_type: str
    source: str
    source_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    detail: str | None


class TimelineRepository:
    """Read-only. One merged query over `audit_logs`, `badge_prints` and
    `notifications`, sorted and paginated in SQL, plus one batched actor
    lookup — a constant number of statements regardless of page size."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def invitation_exists(self, invitation_id: uuid.UUID) -> bool:
        stmt = select(Invitation.id).where(
            Invitation.id == invitation_id, Invitation.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def invitation_id_for_visitor(self, visitor_id: uuid.UUID) -> uuid.UUID | None:
        stmt = (
            select(InvitationVisitor.invitation_id)
            .join(Invitation, Invitation.id == InvitationVisitor.invitation_id)
            .where(
                InvitationVisitor.id == visitor_id,
                InvitationVisitor.deleted_at.is_(None),
                Invitation.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _merged(invitation_id: uuid.UUID) -> Any:
        audit_type = case(
            {action: event.value for action, event in AUDIT_ACTION_TO_EVENT.items()},
            value=AuditLog.action,
        )
        audit = select(
            AuditLog.created_at.label("occurred_at"),
            audit_type.label("event_type"),
            literal("audit").label("source"),
            AuditLog.id.label("source_id"),
            AuditLog.actor_user_id.label("actor_user_id"),
            AuditLog.action.label("detail"),
        ).where(
            AuditLog.entity_type.in_(INVITATION_ENTITY_TYPES),
            AuditLog.entity_id == invitation_id,
            AuditLog.action.in_(list(AUDIT_ACTION_TO_EVENT)),
        )
        badge_type = case(
            (BadgePrint.reprint_reason.is_not(None), TimelineEventType.badge_reprinted.value),
            else_=TimelineEventType.badge_printed.value,
        )
        badge = select(
            BadgePrint.printed_at.label("occurred_at"),
            badge_type.label("event_type"),
            literal("badge").label("source"),
            BadgePrint.id.label("source_id"),
            BadgePrint.printed_by_user_id.label("actor_user_id"),
            BadgePrint.reprint_reason.label("detail"),
        ).where(BadgePrint.visit_id == invitation_id)
        # One row per dispatch: a dispatch fans out to one row per recipient.
        notification = (
            select(
                Notification.created_at.label("occurred_at"),
                literal(TimelineEventType.notification_sent.value).label("event_type"),
                literal("notification").label("source"),
                Notification.id.label("source_id"),
                literal(None, type_=Notification.user_id.type).label("actor_user_id"),
                Notification.title.label("detail"),
            )
            .where(Notification.invitation_id == invitation_id)
            .distinct(Notification.dispatch_id)
            .order_by(Notification.dispatch_id, Notification.created_at)
        )
        return union_all(audit, badge, notification.subquery().select()).subquery("timeline")

    async def list_page(
        self,
        invitation_id: uuid.UUID,
        *,
        occurred_after: datetime | None,
        occurred_before: datetime | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
    ) -> tuple[list[TimelineRow], int]:
        merged = self._merged(invitation_id)
        filters = []
        if occurred_after is not None:
            filters.append(merged.c.occurred_at >= occurred_after)
        if occurred_before is not None:
            filters.append(merged.c.occurred_at <= occurred_before)

        total = (
            await self.session.execute(select(func.count()).select_from(merged).where(*filters))
        ).scalar_one()
        sort_column = getattr(merged.c, sort_by)
        stmt: Select[Any] = (
            select(merged)
            .where(*filters)
            .order_by(
                order_clause(sort_column, sort_order),
                order_clause(merged.c.occurred_at, sort_order),
                merged.c.source,
                merged.c.source_id,
            )
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self.session.execute(stmt)).all()
        return [TimelineRow(*row) for row in rows], total

    async def actor_names(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        stmt = select(User.id, User.full_name).where(User.id.in_(user_ids))
        return {uid: name for uid, name in (await self.session.execute(stmt)).all()}
