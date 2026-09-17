"""The six canonical registration steps and their seeded fields, per
`specs/form-builder/spec.md`'s "Six Canonical Steps Exist By Default" and
"System Fields Are Seeded With a Locked or Toggleable Tier". Field
required/active defaults here match today's hardcoded `invitations`
behavior exactly (`design.md`'s "zero behavior change" goal) — a branch
that never customizes its form still submits/validates as it always has.

This module produces two things from one source of truth:
- `build_default_form_field_specs()` / `build_default_form_step_specs()`:
  plain specs used to materialize real `FormStep`/`FormField` draft rows
  (`service.py::seed_default_form_config`, `platform/service.py::create_tenant`).
- `DEFAULT_EFFECTIVE_FORM`: the same steps/fields already shaped as
  `FormStepOut`-compatible camelCase dicts, used as the effective-form
  fallback when a scope has never been published — see
  `service.py::resolve_effective_form`. No admin action is required for a
  tenant/branch to render or validate against a sensible default.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

_NAMESPACE = uuid.UUID("d8f6e6b2-6f3b-4a8a-9d3a-2f2a6b1c4e10")


def _stable_id(*parts: str) -> uuid.UUID:
    """Deterministic, never-persisted id for the fallback snapshot — stable
    across requests/processes so a `fieldKey`/id pairing a caller observed
    doesn't change from one call to the next.
    """
    return uuid.uuid5(_NAMESPACE, ":".join(parts))


@dataclass
class DefaultFieldSpec:
    key: str
    label: str
    field_type: str
    is_locked: bool
    is_required: bool
    is_active: bool = True
    options: list[str] | None = None
    placeholder: str | None = None
    help_text: str | None = None


@dataclass
class DefaultStepSpec:
    key: str
    name: str
    is_locked: bool
    icon: str | None = None
    description: str | None = None
    fields: list[DefaultFieldSpec] = field(default_factory=list)


DEFAULT_STEP_SPECS: list[DefaultStepSpec] = [
    DefaultStepSpec(
        key="visitor_info",
        name="Visitor Info",
        icon="user",
        is_locked=True,
        fields=[
            DefaultFieldSpec(
                "registration_type",
                "Registration Type",
                "toggle_switch",
                is_locked=True,
                is_required=True,
                options=["individual", "group"],
            ),
            DefaultFieldSpec("full_name", "Full Name", "text", is_locked=True, is_required=True),
            DefaultFieldSpec("email", "Email", "email", is_locked=True, is_required=False),
            DefaultFieldSpec("phone", "Phone", "phone", is_locked=True, is_required=False),
            DefaultFieldSpec(
                "visitor_category",
                "Visitor Category",
                "dropdown_select",
                is_locked=True,
                is_required=True,
            ),
            DefaultFieldSpec(
                "preferred_contact_method",
                "Preferred Contact Method",
                "toggle_switch",
                is_locked=True,
                is_required=True,
                options=["email", "sms"],
            ),
            DefaultFieldSpec(
                "id_proof_type",
                "ID Proof Type",
                "dropdown_select",
                is_locked=False,
                is_required=True,
                options=["Aadhaar Card", "Passport", "Driving License", "Other"],
            ),
            DefaultFieldSpec(
                "id_proof_upload", "Upload ID", "file_upload", is_locked=False, is_required=True
            ),
            DefaultFieldSpec(
                "profile_photo", "Profile Photo", "file_upload", is_locked=False, is_required=True
            ),
        ],
    ),
    DefaultStepSpec(
        key="visit_details",
        name="Visit Details",
        icon="calendar",
        is_locked=True,
        fields=[
            DefaultFieldSpec(
                "purpose_of_visit", "Purpose of Visit", "text", is_locked=True, is_required=True
            ),
            DefaultFieldSpec("host", "Host", "text", is_locked=True, is_required=False),
            DefaultFieldSpec(
                "preferred_visit_date",
                "Preferred Visit Date",
                "date_picker",
                is_locked=True,
                is_required=True,
            ),
            DefaultFieldSpec(
                "preferred_visit_time",
                "Preferred Visit Time",
                "time_picker",
                is_locked=True,
                is_required=True,
            ),
            DefaultFieldSpec(
                "department_to_visit",
                "Department to Visit",
                "text",
                is_locked=True,
                is_required=False,
            ),
            DefaultFieldSpec(
                "expected_duration",
                "Expected Duration",
                "text",
                is_locked=False,
                is_required=True,
            ),
            DefaultFieldSpec(
                "additional_notes",
                "Additional Notes",
                "textarea",
                is_locked=False,
                is_required=False,
            ),
        ],
    ),
    DefaultStepSpec(
        key="carried_items",
        name="Carried Items",
        icon="briefcase",
        is_locked=False,
        fields=[
            DefaultFieldSpec(
                "items",
                "Carried Items",
                "checkbox_list",
                is_locked=False,
                is_required=False,
                options=[
                    "laptop_tablet",
                    "mobile_phone",
                    "camera_recording_device",
                    "usb_drive_storage",
                    "tools_equipment",
                    "food_beverages",
                    "other",
                ],
            ),
            DefaultFieldSpec(
                "item_description",
                "Item Description",
                "textarea",
                is_locked=False,
                is_required=False,
            ),
        ],
    ),
    DefaultStepSpec(
        key="vehicle_info",
        name="Vehicle Info",
        icon="car",
        is_locked=False,
        fields=[
            DefaultFieldSpec(
                "vehicle_type",
                "Vehicle Type",
                "dropdown_select",
                is_locked=True,
                is_required=True,
                options=["2_wheeler", "4_wheeler", "heavy"],
            ),
            DefaultFieldSpec(
                "license_plate", "License Plate", "text", is_locked=True, is_required=True
            ),
            DefaultFieldSpec(
                "make_model", "Make / Model", "text", is_locked=False, is_required=False
            ),
            DefaultFieldSpec("color", "Color", "text", is_locked=False, is_required=False),
        ],
    ),
    DefaultStepSpec(
        key="consent_agreement",
        name="Consent Agreement",
        icon="shield-check",
        is_locked=False,
        fields=[
            DefaultFieldSpec(
                "terms_accepted",
                "Terms & Conditions",
                "toggle_switch",
                is_locked=False,
                is_required=True,
            ),
            DefaultFieldSpec(
                "data_processing_accepted",
                "Data Processing Consent",
                "toggle_switch",
                is_locked=False,
                is_required=True,
            ),
            DefaultFieldSpec(
                "safety_guidelines_accepted",
                "Safety Guidelines",
                "toggle_switch",
                is_locked=False,
                is_required=True,
            ),
        ],
    ),
    DefaultStepSpec(
        key="review_confirm",
        name="Review & Confirm",
        icon="check-circle",
        is_locked=True,
        description="Auto-generated review sheet.",
        fields=[],
    ),
]


def _field_to_effective_dict(
    step_key: str, order_index: int, spec: DefaultFieldSpec
) -> dict[str, Any]:
    return {
        "id": str(_stable_id("field", step_key, spec.key)),
        "stepId": str(_stable_id("step", step_key)),
        "key": spec.key,
        "label": spec.label,
        "placeholder": spec.placeholder,
        "helpText": spec.help_text,
        "fieldType": spec.field_type,
        "isSystem": True,
        "isLocked": spec.is_locked,
        "isActive": spec.is_active,
        "isRequired": spec.is_required,
        "options": spec.options,
        "validationRules": None,
        "visibilityCondition": None,
        "width": "full",
        "orderIndex": order_index,
    }


def _step_to_effective_dict(order_index: int, spec: DefaultStepSpec) -> dict[str, Any]:
    return {
        "id": str(_stable_id("step", spec.key)),
        "branchId": None,
        "key": spec.key,
        "name": spec.name,
        "description": spec.description,
        "icon": spec.icon,
        "isSystem": True,
        "isLocked": spec.is_locked,
        "isActive": True,
        "orderIndex": order_index,
        "fields": [_field_to_effective_dict(spec.key, i, f) for i, f in enumerate(spec.fields)],
    }


DEFAULT_EFFECTIVE_FORM: list[dict[str, Any]] = [
    _step_to_effective_dict(i, spec) for i, spec in enumerate(DEFAULT_STEP_SPECS)
]
"""The fallback effective form for any scope with no published
`FormConfigVersion` — matches today's hardcoded `invitations` behavior
field-for-field. Safe to hand directly to `FormStepOut`'s Pydantic
validator (already camelCase) or serialize as-is into a fresh
`FormConfigVersion.snapshot`.
"""
