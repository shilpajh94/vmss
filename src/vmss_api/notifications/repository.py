import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.notifications.models import DeviceToken


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
