import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Time, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vmss_api.core.database import Base, TimestampMixin


class Invitation(Base, TimestampMixin):
    """One employee-created invitation (API-09) — created already fully
    populated in a single call
    (`merge-invitation-registration-into-creation/design.md` Decision 2).

    Every column below is set at creation time now; there is no more
    intermediate `pending` shell state between "invitation exists" and
    "visit record complete" (that two-phase split, and the separate public
    self-registration endpoint it required, has been removed). `status` is
    `approved` or `submitted` (awaiting approval) depending on the tenant's
    Company auto-approve setting at creation time, and may become
    `approved` later via `POST /invitations/{id}/approve` if it started
    `submitted` (`add-invitation-approval-flow-and-role-resync/design.md`
    Decision 1). It stays a plain string column for future values, three of
    which this class now uses: `denied` (via `POST /invitations/{id}/deny`,
    from `submitted`), `checked_in` (via `POST /invitations/{id}/check-in`,
    from `approved`), and `checked_out` (via
    `POST /invitations/{id}/check-out`, from `checked_in`) — see
    `add-invitation-lifecycle-actions/design.md`. `pending` is no longer
    produced by any code path.

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
    # Set when `status` transitions to "approved" — either resolved
    # immediately at creation (Company.auto_approve_pre_registered_visitors)
    # or later via `POST /invitations/{id}/approve`. NULL until then.
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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

    # --- Visit details: optional catalog ids (visit-info-lookup-api) -------
    # Nullable and purely additive: when a caller supplies one of these, the
    # paired free-text column above is server-side overwritten with the
    # referenced row's canonical name/full_name before persisting (never
    # trusts client-supplied text once an id is given) — see
    # openspec/changes/visit-info-lookup-api/design.md. Omitted entirely,
    # behavior is unchanged from before this feature existed.
    purpose_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("visit_purposes.id"), index=True
    )
    host_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    duration_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("visit_durations.id"), index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id"), index=True
    )

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

    # --- Lifecycle: denial (add-invitation-lifecycle-actions/design.md) ----
    denial_reason: Mapped[str | None] = mapped_column(String(500))
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Lifecycle: check-in / check-out --------------------------------------
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_out_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

    # --- Lifecycle: badge ------------------------------------------------------
    # `badge_number` identifies the visit, not a single physical printout —
    # a reprint keeps it and only changes `badge_storage_key` (design.md
    # Decision 4).
    badge_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    badge_storage_key: Mapped[str | None] = mapped_column(String(500))
    badge_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    badge_reprint_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Lifecycle: watchlist override -----------------------------------------
    # `watchlist_flagged` is set by nothing in this codebase yet — no
    # automatic watchlist/blacklist matching exists (design.md Non-Goals).
    # It exists so `POST /invitations/{id}/watchlist-override` and the
    # check-in gate that reads it have a real column to operate on ahead of
    # that future capability.
    watchlist_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    watchlist_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watchlist_override_reason: Mapped[str | None] = mapped_column(String(500))
    watchlist_override_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id")
    )

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
