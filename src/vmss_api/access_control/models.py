import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin

_NOT_DELETED = text("deleted_at IS NULL")


class Zone(Base, TimestampMixin):
    """A restricted area of a branch (lab, server room, floor 3). Optionally
    narrowed to one `Building` and `Floor`; all of them must belong to
    `branch_id` — the service enforces it, FKs cannot."""

    __tablename__ = "zones"
    __table_args__ = (
        Index(
            "uq_zone_branch_code", "branch_id", "code", unique=True, postgresql_where=_NOT_DELETED
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("buildings.id"))
    floor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("floors.id"))
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ZoneGate(Base):
    """Which gates give entry to a zone (many-to-many). A gate is a registered
    `Device` with `operating_mode="security"` (the Security Gates list), not a
    `SecurityGate` row."""

    __tablename__ = "zone_gates"

    zone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True
    )
    gate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("devices.id"), primary_key=True, index=True
    )


class VisitorCategoryZone(Base):
    """Default allowed zones for a visitor category."""

    __tablename__ = "visitor_category_zones"

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("visitor_categories.id", ondelete="CASCADE"), primary_key=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class InvitationZone(Base):
    """Zones reception explicitly allowed for one visit. When any row exists
    it replaces the visitor category's defaults (design.md Decision 3)."""

    __tablename__ = "invitation_zones"

    invitation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invitations.id", ondelete="CASCADE"), primary_key=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZoneAccessEvent(Base):
    """Append-only gate-scan ledger: every allowed/denied entry and every exit.
    Never updated or soft-deleted, so `created_at` only (database-architecture.md §4).
    `direction` / `decision` / `reason` are plain strings validated at the API
    boundary, like `Device.operating_mode`. `gate_id` is the scanning gate device's id."""

    __tablename__ = "zone_access_events"
    __table_args__ = (
        Index("ix_zone_access_events_invitation_occurred", "invitation_id", "occurred_at"),
        Index("ix_zone_access_events_zone_occurred", "zone_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # CASCADE so the retention purge (`invitations/repository.py::delete_with_children`,
    # which deletes by an explicit table list) is not blocked by a visit's zone events.
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invitations.id", ondelete="CASCADE")
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("zones.id"))
    gate_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("devices.id"))
    direction: Mapped[str] = mapped_column(String(10))
    decision: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(String(40))
    scanned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
