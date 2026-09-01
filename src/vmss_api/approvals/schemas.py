import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from vmss_api.core.schemas import CamelModel


class InvitationApprovalStepStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    skipped = "skipped"
    auto_approved = "auto_approved"


class InvitationApprovalStepOut(CamelModel):
    id: uuid.UUID
    step_order: int
    approver_role_id: uuid.UUID | None
    approver_user_id: uuid.UUID | None
    is_mandatory: bool
    status: InvitationApprovalStepStatus
    acted_by_user_id: uuid.UUID | None
    acted_at: datetime | None
    escalates_at: datetime | None
    auto_approves_at: datetime | None
    delegated_to_user_id: uuid.UUID | None


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
    total_steps: int
    delegated_to_user_id: uuid.UUID | None = None


class InvitationApprovalStepRejectRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)


class InvitationApprovalStepDelegateRequest(CamelModel):
    delegate_user_id: uuid.UUID
