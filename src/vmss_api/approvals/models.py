import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from vmss_api.core.database import Base, TimestampMixin

# Same posture as visitors/models.py's `_NOT_DELETED`: scopes the
# `(invitation_id, step_order)` uniqueness to non-deleted rows so a
# soft-deleted step's slot is reusable.
_NOT_DELETED = text("deleted_at IS NULL")


class InvitationApprovalStep(Base, TimestampMixin):
    """One ordered approval step snapshotted onto an `Invitation` at
    submission time, from the matching `VisitorCategory`'s active
    `ApprovalWorkflowRule` rows (`visitors/models.py`) — a point-in-time
    copy, not a live reference, so editing or deactivating a rule later
    never changes an invitation already in flight
    (invitation-multi-step-approval/design.md Decision 1).

    No ORM `relationship` to `Invitation` or `auth.models.Role`: same
    column-only posture `ApprovalWorkflowRule.approver_role_id` already uses,
    to avoid a cross-feature import cycle for a link this package only ever
    resolves by id, never traverses as an attribute.
    """

    __tablename__ = "invitation_approval_steps"
    __table_args__ = (
        Index(
            "uq_approval_step_invitation_step",
            "invitation_id",
            "step_order",
            unique=True,
            postgresql_where=_NOT_DELETED,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invitations.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    approver_role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"), index=True)
    is_mandatory: Mapped[bool] = mapped_column(default=True)
    # Plain string, not a DB enum — matches `Invitation.status`'s existing
    # convention (design.md Decision 5). One of: pending, approved, rejected,
    # skipped, auto_approved.
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    acted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Raw durations snapshotted from the rule at submission time (immutable,
    # same "snapshot, not a live join" posture as the rest of this row) —
    # kept separately from the computed `escalates_at`/`auto_approves_at`
    # timestamps below because a step's own minute values are needed again
    # *later*, when it becomes the current pending step (every step but the
    # first), and re-reading the live `ApprovalWorkflowRule` at that later
    # moment would let a rule edit made in between retroactively change an
    # in-flight invitation's escalation window — exactly what the snapshot
    # is meant to prevent.
    escalation_minutes: Mapped[int | None] = mapped_column(Integer)
    auto_approve_minutes: Mapped[int | None] = mapped_column(Integer)
    # Computed by adding this step's own escalation_minutes/
    # auto_approve_minutes above to the moment this step became the current
    # pending step — the invitation's submission time for the first step,
    # or the moment the prior step was approved for every step after it. See
    # specs/approvals/spec.md "Escalation and Auto-Approve Timestamps Are
    # Computed but Not Enforced". Null until the step becomes current, or
    # permanently null when the corresponding minute value isn't configured.
    # Nothing in this change acts on either timestamp once it passes.
    escalates_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_approves_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
