import uuid
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from vmss_api.core.schemas import CamelModel

# Whitelisted sort columns per api-conventions.md §1.
VisitorCategorySortableField = Literal["name", "created_at"]
ApprovalWorkflowRuleSortableField = Literal["step_order", "created_at"]


class FormFieldType(StrEnum):
    text = "text"
    textarea = "textarea"
    number = "number"
    date = "date"
    select = "select"
    checkbox = "checkbox"
    email = "email"
    phone = "phone"


class FormFieldDefinition(CamelModel):
    """One field in a visitor category's configurable pre-registration/
    check-in form. `name` is the key visitor-submitted form data will be
    keyed by (the `invitations`/`checkin` features, once built) — snake_case,
    not the display label.
    """

    name: str = Field(max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(max_length=255)
    field_type: FormFieldType
    required: bool = False
    options: list[str] | None = Field(default=None, max_length=50)
    help_text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _select_requires_options(self) -> "FormFieldDefinition":
        if self.field_type == FormFieldType.select and not self.options:
            raise ValueError("A 'select' field must declare a non-empty 'options' list")
        return self


def _ensure_unique_field_names(
    fields: list[FormFieldDefinition],
) -> list[FormFieldDefinition]:
    names = [f.name for f in fields]
    if len(names) != len(set(names)):
        raise ValueError("Form field names must be unique within a category")
    return fields


class VisitorCategoryCreate(CamelModel):
    name: str = Field(max_length=100)
    code: str = Field(max_length=50)
    description: str | None = Field(default=None, max_length=500)
    form_schema: list[FormFieldDefinition] = Field(default_factory=list)

    @field_validator("form_schema")
    @classmethod
    def _validate_form_schema(cls, v: list[FormFieldDefinition]) -> list[FormFieldDefinition]:
        return _ensure_unique_field_names(v)


class VisitorCategoryUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    form_schema: list[FormFieldDefinition] | None = None
    is_active: bool | None = None

    @field_validator("form_schema")
    @classmethod
    def _validate_form_schema(
        cls, v: list[FormFieldDefinition] | None
    ) -> list[FormFieldDefinition] | None:
        return _ensure_unique_field_names(v) if v is not None else v


class VisitorCategoryOut(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    form_schema: list[FormFieldDefinition]
    is_active: bool


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
