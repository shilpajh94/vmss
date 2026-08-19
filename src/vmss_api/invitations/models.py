import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Time, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vmss_api.core.database import Base, TimestampMixin


class Invitation(Base, TimestampMixin):
    """One employee-created invitation (API-09) — created already fully
    populated and `status="submitted"` in a single call
    (`merge-invitation-registration-into-creation/design.md` Decision 2).

    Every column below is set at creation time now; there is no more
    intermediate `pending` shell state between "invitation exists" and
    "visit record complete" (that two-phase split, and the separate public
    self-registration endpoint it required, has been removed). `status`
    stays a plain string column for future values (`cancelled`/`expired`),
    but `pending` is no longer produced by any code path.

    No tracking-token column here: the QR payload handed back at
    confirmation is the plain, human-readable `tracking_id` below
    (`INV-XXXXXXXX`) — API-12 also accepts it for lookup. There is no signed
    token to verify anymore, since there is no unauthenticated write
    endpoint left that needed one to resolve tenancy.
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    # Nullable: a walk-in registration (`source="visitor_walk_in"`, API-13) has
    # no authenticated staff creator — see
    # add-walkin-visitor-registration/design.md Decision 1. Every existing row
    # (staff pre-registration) still has a value here.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), index=True
    )

    # "staff_pre_registration" (API-09, via `POST /invitations`) or
    # "visitor_walk_in" (API-13, via `POST /registrations/walk-in`) — see
    # `RegistrationSource` in `schemas.py`. Both channels write the same
    # `Invitation` row shape; this column is the only thing distinguishing
    # them (add-walkin-visitor-registration/design.md Decision 1).
    source: Mapped[str] = mapped_column(String(30), default="staff_pre_registration")
    registration_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    tracking_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Primary contact ---------------------------------------------------
    # Set (partially) at creation; fully overwritten by self-registration —
    # see the class docstring.
    primary_contact_full_name: Mapped[str] = mapped_column(String(255))
    primary_contact_email: Mapped[str | None] = mapped_column(String(255))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50))
    primary_contact_preferred_contact_method: Mapped[str] = mapped_column(String(10))
    primary_contact_id_proof_type: Mapped[str | None] = mapped_column(String(50))
    primary_contact_id_proof_storage_key: Mapped[str | None] = mapped_column(String(500))

    # --- Visit details (self-registration only) -----------------------------
    purpose_of_visit: Mapped[str | None] = mapped_column(String(255))
    host_name_or_email: Mapped[str | None] = mapped_column(String(255))
    preferred_visit_date: Mapped[date | None] = mapped_column(Date())
    preferred_visit_time: Mapped[time | None] = mapped_column(Time())
    expected_duration: Mapped[str | None] = mapped_column(String(50))
    department_to_visit: Mapped[str | None] = mapped_column(String(255))
    additional_notes: Mapped[str | None] = mapped_column(String(2000))

    # --- Carried items -------------------------------------------------------
    # JSONB list, not a child table: items have no independent identity or
    # per-row actions of their own, unlike visitors/vehicles below — same
    # posture as VisitorCategory.form_schema (design.md Decision 8).
    carried_items: Mapped[list[str]] = mapped_column(JSONB, default=list)
    carried_items_description: Mapped[str | None] = mapped_column(String(2000))

    # --- Consent (security-architecture.md §4) --------------------------------
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    data_processing_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_guidelines_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `lazy="raise"` (not the SQLAlchemy default lazy-load, and not "noload")
    # forces every query touching these to eager-load explicitly via
    # `selectinload` (query-performance.md §1) — a forgotten eager-load fails
    # loudly here instead of silently serializing an empty list.
    visitors: Mapped[list["InvitationVisitor"]] = relationship(lazy="raise")
    vehicles: Mapped[list["InvitationVehicle"]] = relationship(lazy="raise")


class InvitationVisitor(Base, TimestampMixin):
    """One co-visitor in a `group` invitation's self-registration submission.
    Never created for an `individual` invitation — the primary contact is the
    sole visitor there (spec.md "Visitor List Matches Registration Type").
    """

    __tablename__ = "invitation_visitors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invitations.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    id_proof_type: Mapped[str] = mapped_column(String(50))
    id_proof_storage_key: Mapped[str] = mapped_column(String(500))


class InvitationVehicle(Base, TimestampMixin):
    """One vehicle declared in a self-registration submission — zero or more
    per invitation, regardless of `registration_type`.
    """

    __tablename__ = "invitation_vehicles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invitations.id"), index=True)
    vehicle_type: Mapped[str] = mapped_column(String(20))
    license_plate: Mapped[str] = mapped_column(String(50))
    make_model: Mapped[str | None] = mapped_column(String(255))
    color: Mapped[str | None] = mapped_column(String(50))
