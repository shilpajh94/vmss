import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    Uuid,
    text,
)
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

    `tracking_id` below (`INV-XXXXXXXX`) is the human-readable identity
    API-12 accepts for lookup and manual desk entry. The QR *scanned* at
    check-in is a separate, encrypted token — see `InvitationQRCode` below
    and `invitations/qr_token.py` — not this column
    (`add-qr-checkin-security/design.md`).
    """

    __tablename__ = "invitations"
    # Dashboard analytics range scans (live-dashboards-and-analytics
    # design.md D4); mirrors alembic_tenant revision 6791c5e6a421.
    __table_args__ = (
        Index(
            "ix_invitations_branch_visit_date",
            "branch_id",
            "preferred_visit_date",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_invitations_branch_checked_in_at",
            "branch_id",
            "checked_in_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Digits-only phone prefill lookup (reception-phone-prefill-lookup
        # design.md); mirrors alembic_tenant revision a7c3e1d9b5f2.
        Index(
            "ix_invitations_primary_contact_phone_digits",
            text(r"regexp_replace(primary_contact_phone, '\D', '', 'g')"),
            postgresql_where=text("deleted_at IS NULL AND primary_contact_phone IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), index=True)
    # Building the visitor selected at registration; when NULL the detail view
    # falls back to the department's building (see `InvitationRepository.get_location`).
    building_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("buildings.id"), index=True
    )
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
    # Nullable at the DB level (pre-existing rows have none), but required on
    # `InvitationCreate` going forward — see
    # invitation-multi-step-approval/design.md Decision 1. Drives which
    # `ApprovalWorkflowRule`s (visitors/models.py) get snapshotted into this
    # invitation's own `InvitationApprovalStep` rows at submission time.
    visitor_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("visitor_categories.id"), index=True
    )
    tracking_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # 8-digit code sent by SMS instead of a QR image; only issued at approval
    # for contacts preferring `sms` (add-sms-numeric-checkin-code).
    checkin_code: Mapped[str | None] = mapped_column(String(8), unique=True, index=True)
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
    # Indexed (`a1b2c3d4e5f6`): the `visitor_return_visit` capability looks up
    # a verified identifier's prior visits by exact match on one of these two
    # columns.
    primary_contact_email: Mapped[str | None] = mapped_column(String(255), index=True)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50), index=True)
    primary_contact_preferred_contact_method: Mapped[str] = mapped_column(String(10))
    primary_contact_id_proof_type: Mapped[str | None] = mapped_column(String(50))
    # Deliberately never resolved to a URL or exposed on any response schema
    # (add-avatar-upload-and-verify-image-storage/design.md Decision 5) —
    # unlike the photo/badge/QR image keys elsewhere in this file, an ID-proof
    # scan is the most sensitive document this system stores. Per
    # security-architecture.md §4, "access to raw document images is itself a
    # permission, not implied by can view visitor record" — no such
    # permission or viewing endpoint exists yet, so this stays write-only
    # until a real requirement (and its own permission) is proposed.
    primary_contact_id_proof_storage_key: Mapped[str | None] = mapped_column(String(500))
    # Optional profile photo (checkin-approval-workflow-improvements) —
    # nullable, unlike the ID-proof storage key, since capturing a photo is
    # never required.
    primary_contact_photo_storage_key: Mapped[str | None] = mapped_column(String(500))
    # Answers for admin-authored Visitor Info fields (`form-builder`'s
    # "Fully Configurable Steps Accept Admin-Authored Fields"), keyed by
    # field key — the primary contact's counterpart to
    # `InvitationVisitor.custom_field_values` below. Kept separate from
    # `custom_field_values` (invitation-level answers) so the two scopes
    # never share a key namespace on the same row
    # (`add-generic-custom-field-support/design.md` Decision 1).
    primary_contact_custom_field_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # --- Visit details (self-registration only) -----------------------------
    purpose_of_visit: Mapped[str | None] = mapped_column(String(255))
    host_name_or_email: Mapped[str | None] = mapped_column(String(255))
    preferred_visit_date: Mapped[date | None] = mapped_column(Date())
    preferred_visit_time: Mapped[time | None] = mapped_column(Time())
    # Snapshot of `preferred_visit_date`/`preferred_visit_time` immediately
    # before the most recent `PATCH /invitations/{id}/reschedule` overwrote
    # them (`add-reschedule-history/design.md`) — NULL until the invitation
    # has been rescheduled at least once. `reschedule_if_eligible` populates
    # all four of these columns in the same `UPDATE` that changes the
    # current date/time, so they always describe the immediately-prior
    # schedule, not necessarily the invitation's original one.
    previous_preferred_visit_date: Mapped[date | None] = mapped_column(Date())
    previous_preferred_visit_time: Mapped[time | None] = mapped_column(Time())
    rescheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reschedule_count: Mapped[int] = mapped_column(Integer(), default=0)
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

    # --- Point of contact (add-invitation-point-of-contact) -----------------
    # Distinct from `host_id`/`host_name_or_email` above: the host is who the
    # visitor is meeting, resolved only via the `approvals` workflow (or,
    # for a single-step workflow, by directly approving its only step — see
    # `approvals/service.py::approve_step`). The point of contact is who to
    # actually reach about the visit's logistics, and is set directly via
    # `PATCH /invitations/{id}/edit` by any `invitations:approve` holder at
    # any time, regardless of the invitation's current approval step/level.
    # Exactly one of `poc_user_id`/`poc_role_id` may be set, never both — at
    # most one, unlike `InvitationApprovalStep`'s exactly-one XOR, since a
    # point of contact is optional. Enforced by the
    # `ck_invitations_poc_at_most_one` CHECK constraint (migration-only,
    # same convention as `InvitationApprovalStep.approver_role_id`/
    # `approver_user_id` above it — not declared in `__table_args__` here).
    poc_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    poc_role_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("roles.id"), index=True)
    # Snapshotted display name (the user's full_name or the role's name) at
    # the moment POC was last set — same convention as `host_name_or_email`,
    # so rendering it (visit info, the visitor's edit-confirmation email)
    # never needs an extra join.
    poc_name: Mapped[str | None] = mapped_column(String(255))

    # --- Carried items -------------------------------------------------------
    # JSONB list, not a child table: items have no independent identity or
    # per-row actions of their own, unlike visitors/vehicles below — same
    # posture as VisitorCategory.form_schema (design.md Decision 8).
    carried_items: Mapped[list[str]] = mapped_column(JSONB, default=list)
    carried_items_description: Mapped[str | None] = mapped_column(String(2000))

    # --- Consent (security-architecture.md §4) --------------------------------
    # `terms_accepted`/`data_processing_accepted`/`safety_guidelines_accepted`
    # below are **deprecated** (`openspec/changes/form-builder/`): no longer
    # written by `create_invitation`, which now records every accepted
    # consent key (branch-configured, defaulting to these same three) in
    # `consents` instead. Left in place for one release's burn-in — per
    # design.md's migration plan — before a follow-up migration drops them;
    # every row created from here on simply carries their column default.
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    data_processing_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_guidelines_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    consents: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Custom fields (add-generic-custom-field-support) --------------------
    # Answers for admin-authored fields on Visit Details, Carried Items,
    # Consent Agreement, or a custom step — every step whose own fields have
    # no per-entity structure of their own, so their custom-field answers
    # are recorded once per invitation. Keyed by field key. Visitor Info and
    # Vehicle Info custom-field answers live on `InvitationVisitor`/
    # `primary_contact_custom_field_values` and `InvitationVehicle` instead
    # (`design.md` Decision 1/2).
    custom_field_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # --- Repeatable field group answers (add-repeatable-field-groups) --------
    # Keyed by `FormFieldGroup.key`, holding an ordered list of per-instance
    # answer maps, for any repeatable group other than the seeded Vehicle
    # Info/Visitor Info groups (which keep their own dedicated
    # `InvitationVehicle`/`InvitationVisitor` tables — design.md Decision 2/3).
    group_field_values: Mapped[dict[str, list[dict[str, Any]]]] = mapped_column(JSONB, default=dict)

    # --- Lifecycle: denial (add-invitation-lifecycle-actions/design.md) ----
    denial_reason: Mapped[str | None] = mapped_column(String(500))
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Lifecycle: approval revert (add-invitation-approval-revert) --------
    # Latest revert only — overwritten on each revert; the full history is
    # in `audit_logs` (design.md Decision 1).
    approval_reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_reverted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id")
    )
    approval_revert_reason: Mapped[str | None] = mapped_column(String(500))

    # --- Lifecycle: check-in / check-out --------------------------------------
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_out_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    # True only when the visit-lifecycle sweep closed an expired check-in
    # (`checked_out_at` is then the invitation's `expires_at`, not an observed
    # exit); every manual check-out writes it back to False
    # (auto-checkout-and-archive-no-shows/design.md D3).
    checked_out_automatically: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Lifecycle: archive (auto-checkout-and-archive-no-shows) ---------------
    # Set when the sweep moves an approved, never-admitted invitation to
    # `status="archived"` after its `expires_at`. Kept after a reschedule out
    # of `archived` as history; overwritten if archived again (design.md D4).
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Device that performed the most recent state-changing check-in/out
    # (add-kiosk-device-approval-and-traceability/design.md Decision 7). Null
    # when the caller sent no `device-id` header.
    check_in_device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("devices.id"), index=True
    )
    check_out_device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("devices.id"), index=True
    )

    # --- Lifecycle: QR check-in scan state (add-qr-checkin-security) -----------
    # Deliberately parallel to, not derived from, `status` above: `status`
    # keeps carrying its existing `checked_in`/`checked_out` values for the
    # staff-authenticated and tracking-ID check-in paths unchanged, while
    # `check_in_status` is the gate condition the QR scan endpoint reads and
    # writes — both are updated together by that endpoint so nothing reading
    # `status` (e.g. the "who's inside" emergency report) needs to change.
    # `unused` -> `checked_in` -> `checked_out`, never backward. Plain string
    # column, same rationale as `status`'s own docstring (avoids an
    # `ALTER TYPE` migration for a native Postgres enum).
    check_in_status: Mapped[str] = mapped_column(String(20), default="unused")

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
    # Nullable (form-builder): whether ID proof is captured at all for a
    # visitor is now branch-configurable (`specs/form-builder/spec.md`'s
    # Visitor Info toggleable tier), not unconditionally mandatory.
    id_proof_type: Mapped[str | None] = mapped_column(String(50))
    # Deliberately never resolved to a URL or exposed on any response schema —
    # see the matching comment on `Invitation.primary_contact_id_proof_storage_key`
    # above (add-avatar-upload-and-verify-image-storage/design.md Decision 5).
    id_proof_storage_key: Mapped[str | None] = mapped_column(String(500))
    # Optional profile photo (checkin-approval-workflow-improvements).
    photo_storage_key: Mapped[str | None] = mapped_column(String(500))
    # Answers for admin-authored Visitor Info fields, keyed by field key —
    # this visitor's own copy, independent of any other visitor's answer
    # for the same field (add-generic-custom-field-support/design.md
    # Decision 2).
    custom_field_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class InvitationQRCode(Base, TimestampMixin):
    """The encrypted check-in token issued for an invitation, and where its
    rendered QR image was persisted (`add-qr-checkin-security/design.md`).
    One row per invitation, generated once at the moment it becomes
    `approved` and reused for any later resend/reprint — never regenerated
    on each notification send the way the plain-tracking-ID QR used to be.

    No `expires_at` here — expiry is always read live from
    `Invitation.expires_at` at scan time, so there is exactly one place
    that value can drift out of sync (deliberately avoided; see design.md).
    """

    __tablename__ = "invitation_qr_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invitations.id"), unique=True, index=True
    )
    qr_token: Mapped[str] = mapped_column(String(500))
    image_storage_key: Mapped[str] = mapped_column(String(500))


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
    # Answers for admin-authored Vehicle Info fields beyond the locked
    # license-plate field, keyed by field key — this vehicle's own copy
    # (add-generic-custom-field-support/design.md Decision 2).
    custom_field_values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
