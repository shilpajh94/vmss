import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from vmss_api.core.schemas import CamelModel


class FormFieldType(StrEnum):
    text = "text"
    email = "email"
    phone = "phone"
    number = "number"
    dropdown_select = "dropdown_select"
    date_picker = "date_picker"
    time_picker = "time_picker"
    toggle_switch = "toggle_switch"
    checkbox_list = "checkbox_list"
    file_upload = "file_upload"
    textarea = "textarea"
    dynamic_table = "dynamic_table"
    rich_text_block = "rich_text_block"
    signature_pad = "signature_pad"
    static_text = "static_text"


# Field types whose value is meaningless without a declared option set — see
# specs/form-builder/spec.md "Field Types Are Constrained To a Supported
# Set". `toggle_switch` MAY also carry options (e.g. Registration Type:
# individual/group) but doesn't require them — some toggles are a plain
# on/off with no named option list.
OPTION_REQUIRED_TYPES = frozenset({FormFieldType.dropdown_select, FormFieldType.checkbox_list})


class FieldWidth(StrEnum):
    half = "half"
    full = "full"


class ConditionOperator(StrEnum):
    equals = "equals"
    not_equals = "not_equals"


class VisibilityCondition(CamelModel):
    field_key: str = Field(max_length=100)
    operator: ConditionOperator = ConditionOperator.equals
    value: str = Field(max_length=255)


class ValidationRules(CamelModel):
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    min_value: float | None = None
    max_value: float | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("minLength must not be greater than maxLength")
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("minValue must not be greater than maxValue")
        return self


class FormFieldCreate(CamelModel):
    key: str = Field(max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(max_length=255)
    placeholder: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=1000)
    field_type: FormFieldType
    is_required: bool = False
    # Which of the step's field groups this field belongs to, or `None` to
    # leave it ungrouped (a flat step-level field) — see
    # `specs/form-builder/spec.md` "A Step's Fields May Be Organized Into
    # Named, Repeatable Field Groups".
    group_id: uuid.UUID | None = None
    options: list[Annotated[str, Field(max_length=100)]] | None = Field(default=None, max_length=50)
    validation_rules: ValidationRules | None = None
    visibility_condition: VisibilityCondition | None = None
    width: FieldWidth = FieldWidth.full

    @model_validator(mode="after")
    def _check_options(self) -> Self:
        if self.field_type in OPTION_REQUIRED_TYPES and not self.options:
            raise ValueError(f"A '{self.field_type}' field must declare a non-empty 'options' list")
        return self

    @model_validator(mode="after")
    def _check_static_text(self) -> Self:
        if self.field_type == FormFieldType.static_text:
            if self.is_required:
                raise ValueError("A 'static_text' field cannot be required — it collects no value")
            if not self.help_text or not self.help_text.strip():
                raise ValueError("A 'static_text' field must declare non-empty 'helpText' content")
        return self


class FormFieldUpdate(CamelModel):
    group_id: uuid.UUID | None = None
    label: str | None = Field(default=None, max_length=255)
    placeholder: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=1000)
    field_type: FormFieldType | None = None
    is_active: bool | None = None
    is_required: bool | None = None
    options: list[Annotated[str, Field(max_length=100)]] | None = Field(default=None, max_length=50)
    validation_rules: ValidationRules | None = None
    visibility_condition: VisibilityCondition | None = None
    width: FieldWidth | None = None


class FormFieldOut(CamelModel):
    id: uuid.UUID
    step_id: uuid.UUID
    group_id: uuid.UUID | None
    key: str
    label: str
    placeholder: str | None
    help_text: str | None
    field_type: FormFieldType
    is_system: bool
    is_locked: bool
    is_active: bool
    is_required: bool
    options: list[str] | None
    validation_rules: ValidationRules | None
    visibility_condition: VisibilityCondition | None
    width: FieldWidth
    order_index: int


class FormFieldGroupCreate(CamelModel):
    key: str = Field(max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(max_length=255)
    is_repeatable: bool = False
    min_instances: int | None = Field(default=None, ge=0)
    max_instances: int | None = Field(default=None, ge=0)
    # Same shape/rules as `FormFieldCreate.visibility_condition` — see
    # `specs/form-builder/spec.md` "A Field Group May Declare Conditional
    # Visibility". Independent of `is_repeatable`.
    visibility_condition: VisibilityCondition | None = None

    @model_validator(mode="after")
    def _check_instance_range(self) -> Self:
        if (
            self.min_instances is not None
            and self.max_instances is not None
            and self.min_instances > self.max_instances
        ):
            raise ValueError("minInstances must not be greater than maxInstances")
        return self


class FormFieldGroupUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    is_repeatable: bool | None = None
    min_instances: int | None = Field(default=None, ge=0)
    max_instances: int | None = Field(default=None, ge=0)
    visibility_condition: VisibilityCondition | None = None

    @model_validator(mode="after")
    def _check_instance_range(self) -> Self:
        if (
            self.min_instances is not None
            and self.max_instances is not None
            and self.min_instances > self.max_instances
        ):
            raise ValueError("minInstances must not be greater than maxInstances")
        return self


class FormFieldGroupOut(CamelModel):
    id: uuid.UUID
    step_id: uuid.UUID
    key: str
    name: str
    is_system: bool
    is_locked: bool
    is_repeatable: bool
    min_instances: int | None
    max_instances: int | None
    visibility_condition: VisibilityCondition | None
    order_index: int
    field_ids: list[uuid.UUID] = Field(default_factory=list)


class FormStepCreate(CamelModel):
    key: str = Field(max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=50)


class FormStepUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class FormStepOut(CamelModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None
    key: str
    name: str
    description: str | None
    icon: str | None
    is_system: bool
    is_locked: bool
    is_active: bool
    order_index: int
    fields: list[FormFieldOut] = Field(default_factory=list)
    groups: list[FormFieldGroupOut] = Field(default_factory=list)


class ReorderRequest(CamelModel):
    ordered_ids: list[uuid.UUID] = Field(min_length=1)


class PublishOut(CamelModel):
    branch_id: uuid.UUID | None
    version: int
    published_at: datetime
