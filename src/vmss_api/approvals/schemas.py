import uuid
from enum import StrEnum

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class InvitationApprovalStepStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    skipped = "skipped"
    auto_approved = "auto_approved"


class CurrentApprovalStepOut(CamelModel):
    """The "what am I waiting on" shape embedded in
    `InvitationOut`/`InvitationDetailOut`/`InvitationTrackingOut`. Carries
    `id` so a caller can invoke `POST /invitations/{id}/approval-
    steps/{stepId}/approve` (or `.../reject`) directly, without a separate
    lookup (add-approval-step-id-and-host-routing/design.md — knowing a
    step's `id` grants no privilege by itself; both mutating endpoints
    independently re-check permission and role/host/override match).
    Exactly one of `approver_role_id`/`approver_user_id` is set, mirroring
    `InvitationApprovalStep`'s own invariant. `delegated_to_user_id` is
    null unless the host has delegated this step
    (invitation-relevant-to-me-and-delegation/specs/approvals/spec.md
    "Host Delegates the Step Following Their Own to a Specific Person").
    """

    id: uuid.UUID
    step_order: int
    approver_role_id: uuid.UUID | None
    approver_user_id: uuid.UUID | None
    total_steps: int = Field(
        description=(
            "Count of this invitation's own snapshotted approval steps — a "
            "point-in-time copy taken at submission, never a live re-read of "
            "the category's current rules. Equal to the visitor category's "
            "active ApprovalWorkflowRule count at submission time, or 1 if "
            "the category had none (the only case a synthetic step gets "
            "added). Matches the row count from "
            "GET /approval-workflow-rules?visitorCategoryId=... as of "
            "submission time (or 1 if that returns no rows) — it will only "
            "diverge from what that endpoint reports *now* if the category's "
            "rules were edited after this invitation was submitted, which is "
            "expected, not a stale read."
        )
    )
    delegated_to_user_id: uuid.UUID | None = None


class InvitationApprovalStepRejectRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)


class InvitationApprovalStepDelegateRequest(CamelModel):
    delegate_user_id: uuid.UUID
