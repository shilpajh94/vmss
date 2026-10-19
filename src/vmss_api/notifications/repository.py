import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.notifications.models import DeviceToken, Notification


class DeviceTokenRepository:
    """Operates on `device_tokens` in whichever tenant schema `session` is
    bound to (database-architecture.md §2). Not a `TenantScopedRepository`
    subclass — `DeviceToken` is hard-deleted, not soft-deleted (see its own
    docstring), so there's no `deleted_at` filter for that base class to add;
    same posture `auth/repository.py::UserRepository`'s `UserBranchRole`
    methods already have.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_token(self, fcm_token: str) -> DeviceToken | None:
        stmt = select(DeviceToken).where(DeviceToken.fcm_token == fcm_token)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_by_token(
        self, *, user_id: uuid.UUID, fcm_token: str, platform: str
    ) -> DeviceToken:
        """Re-registering an already-known token updates its owner/platform/
        `last_seen_at` in place rather than inserting a duplicate row for the
        same physical device — including reassigning it to a *different*
        user than the one it was last registered to, since a device
        (browser/app install) can only ever be one person's at a time
        (specs/notifications/spec.md).
        """
        existing = await self.get_by_token(fcm_token)
        if existing is not None:
            existing.user_id = user_id
            existing.platform = platform
            existing.last_seen_at = datetime.now(UTC)
            await self.session.flush()
            return existing
        device = DeviceToken(
            id=uuid.uuid4(),
            user_id=user_id,
            fcm_token=fcm_token,
            platform=platform,
            last_seen_at=datetime.now(UTC),
        )
        self.session.add(device)
        await self.session.flush()
        return device

    async def delete_owned_by_user(self, *, user_id: uuid.UUID, fcm_token: str) -> None:
        """A no-op (not an error) when `fcm_token` doesn't exist or belongs to
        someone else — the `WHERE` simply matches zero rows
        (specs/notifications/spec.md "Removing an unknown token is not an
        error").
        """
        stmt = delete(DeviceToken).where(
            DeviceToken.fcm_token == fcm_token, DeviceToken.user_id == user_id
        )
        await self.session.execute(stmt)

    async def list_tokens_for_users(self, user_ids: Sequence[uuid.UUID]) -> list[DeviceToken]:
        if not user_ids:
            return []
        stmt = select(DeviceToken).where(DeviceToken.user_id.in_(user_ids))
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_by_tokens(self, tokens: Sequence[str]) -> None:
        """Called when FCM reports a token as no-longer-registered
        (specs/notifications/spec.md "An Invalid or Expired Device Token Is
        Removed on Delivery Failure") — a single bulk `DELETE ... WHERE
        fcm_token IN (...)` per query-performance.md §3, not a per-token loop.
        """
        if not tokens:
            return
        stmt = delete(DeviceToken).where(DeviceToken.fcm_token.in_(tokens))
        await self.session.execute(stmt)


class NotificationRepository:
    """In-app notifications in whichever tenant schema `session` is bound to.
    Every read/update method takes the caller's `user_id` and filters on it —
    there is no method that returns or changes another user's rows
    (fix-web-push-and-add-notification-feed design.md D3). Hard-deleted, so
    not a `TenantScopedRepository` (same posture as `DeviceTokenRepository`).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_for_users(
        self,
        *,
        dispatch_id: uuid.UUID,
        user_ids: Sequence[uuid.UUID],
        title: str,
        body: str,
        data: dict[str, Any],
    ) -> None:
        """One bulk insert per dispatch (query-performance.md §3). The unique
        `(dispatch_id, user_id)` makes a redelivered dispatch a no-op
        (background-jobs.md §2).
        """
        if not user_ids:
            return
        stmt = (
            insert(Notification)
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "dispatch_id": dispatch_id,
                        "user_id": user_id,
                        "title": title,
                        "body": body,
                        "data": data,
                    }
                    for user_id in dict.fromkeys(user_ids)
                ]
            )
            .on_conflict_do_nothing(constraint="uq_notifications_dispatch_user")
        )
        await self.session.execute(stmt)

    async def list_page(
        self, user_id: uuid.UUID, *, unread_only: bool, page: int, page_size: int
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        total_stmt = select(func.count()).select_from(Notification).where(*conditions)
        total = (await self.session.execute(total_stmt)).scalar_one()
        stmt = (
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def mark_read(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        """Returns the caller's notification, read. `None` when the id is
        unknown or belongs to someone else — the caller can't tell which.
        An already-read row is returned unchanged, keeping its `read_at`.
        """
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
            .returning(Notification)
        )
        updated = (await self.session.execute(stmt)).scalar_one_or_none()
        if updated is not None:
            return updated
        existing_stmt = select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
        return (await self.session.execute(existing_stmt)).scalar_one_or_none()

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=func.now())
        )
        await self.session.execute(stmt)

    async def purge_older_than(self, cutoff: datetime) -> int:
        stmt = delete(Notification).where(Notification.created_at < cutoff)
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        return result.rowcount
