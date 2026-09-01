import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
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
