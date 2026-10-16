import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin


class Device(Base, TimestampMixin):
    """A kiosk or security device that registered itself from the mobile app
    and is approved by an admin before it can check visitors in or out.
    Independent of the admin-managed `kiosks.models.Kiosk` list and of the
    global-schema `RegistrationDeviceKey` credential — see
    add-kiosk-device-approval-and-traceability/design.md Decision 1.

    `operating_mode` / `approval_status` are plain strings validated at the
    API boundary (`schemas.py`), same posture as `SecurityGate.gate_type`.
    "Disabled" is `approval_status='approved'` with `is_active=false`.
    """

    __tablename__ = "devices"
    # Scoped to live rows so a soft-deleted device's id can re-register.
    __table_args__ = (
        Index(
            "uq_devices_device_id",
            "device_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("buildings.id"), index=True
    )
    operating_mode: Mapped[str] = mapped_column(String(20), index=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", name="fk_devices_approved_by_user_id")
    )


class TenantSettings(Base, TimestampMixin):
    """Single-row, typed tenant-level admin settings. A missing row means
    every setting is at its default (Decision 9).
    """

    __tablename__ = "tenant_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    enforce_kiosk_location_validation: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
