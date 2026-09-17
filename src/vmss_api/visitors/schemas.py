import uuid
from enum import StrEnum
from typing import Literal

from pydantic import Field

from vmss_api.core.schemas import CamelModel

# Whitelisted sort columns per api-conventions.md §1.
VisitorCategorySortableField = Literal["name", "created_at"]
ApprovalWorkflowRuleSortableField = Literal["step_order", "created_at"]


class NdaRequirement(StrEnum):
    digital = "digital"
    signed_pdf = "signed_pdf"
    optional = "optional"
    none = "none"


class EscortRequirement(StrEnum):
    self_escort = "self_escort"
    access_logs_only = "access_logs_only"
    always_required = "always_required"
    gate_check_in_only = "gate_check_in_only"


class ApprovalWorkflowRuleStatus(StrEnum):
    """`?status=` filter value for `GET /approval-workflow-rules`, mapped
    onto `ApprovalWorkflowRule.is_active` — matches the pattern of
    `org_structure.schemas.ActiveStatus` but kept local to this module
    rather than importing across features for one small enum.
    """

    active = "active"
    inactive = "inactive"


class VisitorCategoryCreate(CamelModel):
    name: str = Field(max_length=100)
    code: str = Field(max_length=50)
    description: str | None = Field(default=None, max_length=500)
    badge_color: str | None = Field(default=None, max_length=30)
    nda_requirement: NdaRequirement | None = None
    escort_requirement: EscortRequirement | None = None
    max_duration_minutes: int | None = Field(default=None, ge=1)


class VisitorCategoryUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    badge_color: str | None = Field(default=None, max_length=30)
    nda_requirement: NdaRequirement | None = None
    escort_requirement: EscortRequirement | None = None
    max_duration_minutes: int | None = Field(default=None, ge=1)


class VisitorCategoryOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    is_active: bool
    badge_color: str | None
    nda_requirement: str | None
    escort_requirement: str | None
    max_duration_minutes: int | None


class ApprovalWorkflowRuleCreate(CamelModel):
    visitor_category_id: uuid.UUID
    step_order: int = Field(ge=1)
    approver_role_id: uuid.UUID
    is_mandatory: bool = True
    escalation_minutes: int | None = Field(default=None, ge=1)
    auto_approve_minutes: int | None = Field(default=None, ge=1)


class ApprovalWorkflowRuleUpdate(CamelModel):
    step_order: int | None = Field(default=None, ge=1)
    approver_role_id: uuid.UUID | None = None
    is_mandatory: bool | None = None
    escalation_minutes: int | None = Field(default=None, ge=1)
    auto_approve_minutes: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class ApprovalWorkflowRuleOut(CamelModel):
    id: uuid.UUID
    visitor_category_id: uuid.UUID
    step_order: int
    approver_role_id: uuid.UUID
    is_mandatory: bool
    escalation_minutes: int | None
    auto_approve_minutes: int | None
    is_active: bool
