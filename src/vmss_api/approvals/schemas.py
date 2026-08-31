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
    approver_role_id: uuid.UUID
    is_mandatory: bool
    status: InvitationApprovalStepStatus
    acted_by_user_id: uuid.UUID | None
    acted_at: datetime | None
    escalates_at: datetime | None
    auto_approves_at: datetime | None


class CurrentApprovalStepOut(CamelModel):
    """The minimal "what am I waiting on" shape embedded in
    `InvitationOut`/`InvitationTrackingOut` (design.md Decision 7) — a full
    `InvitationApprovalStepOut` carries fields (e.g. `id`) a tracking caller
    has no use for and shouldn't need to know about.
    """

    step_order: int
    approver_role_id: uuid.UUID
    total_steps: int


class InvitationApprovalStepRejectRequest(CamelModel):
    reason: str = Field(min_length=1, max_length=500)
