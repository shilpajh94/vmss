import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base


class DeviceToken(Base):
    """One push-notification device registration — one row per (user,
    physical browser/app install). Hard-deleted on unregister or
    reassignment, not soft-deleted: the registration itself is disposable
    state, same posture as `auth/models.py::UserBranchRole`
    (database-architecture.md §4) — there is no compliance/audit reason to
    keep a record of a device a user no longer has.

    `fcm_token` is globally unique (not per-user): a token identifies one
    physical device, so re-registering the same token under a different user
    reassigns it rather than creating a second row for the same device
    (specs/notifications/spec.md "A Staff User Registers a Device for Push
    Notifications").
    """

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    # "web" / "android" / "ios" — see `schemas.py::DevicePlatform`. Plain
    # string column, not a DB enum, matching `Invitation.status`'s existing
    # convention in this codebase.
    platform: Mapped[str] = mapped_column(String(20))
    fcm_token: Mapped[str] = mapped_column(String(4096), unique=True, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """One in-app notification for one recipient — the persisted copy of a
    push dispatch (fix-web-push-and-add-notification-feed design.md D1/D2),
    written whether or not the recipient has a registered device, so the
    portal's bell can show it regardless of browser push state.

    `(dispatch_id, user_id)` is unique so a Celery redelivery of the same
    dispatch is an `ON CONFLICT DO NOTHING`, never a duplicate. Hard-deleted
    by the 90-day purge, not soft-deleted — disposable UI state with no
    compliance value, the same posture as `DeviceToken`, hence no
    `TimestampMixin` (which carries `deleted_at`).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dispatch_id", "user_id", name="uq_notifications_dispatch_user"),
        Index("ix_notifications_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    dispatch_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
