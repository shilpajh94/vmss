"""Dynamic, branch-configured validation consulted by
`invitations/service.py::create_invitation` after `InvitationCreate`'s
Pydantic (structural) validation — see
`openspec/changes/form-builder/design.md` Decision 5. Works off the
resolved effective-form snapshot
(`form_builder/service.py::resolve_effective_form`), a plain JSON-shaped
list of step dicts, not the database directly.
"""

from typing import Any


def _find_step(effective_form: list[dict[str, Any]], step_key: str) -> dict[str, Any] | None:
    return next((step for step in effective_form if step["key"] == step_key), None)


def _find_field(
    effective_form: list[dict[str, Any]], step_key: str, field_key: str
) -> dict[str, Any] | None:
    step = _find_step(effective_form, step_key)
    if step is None:
        return None
    return next((field for field in step["fields"] if field["key"] == field_key), None)


def is_field_required(
    effective_form: list[dict[str, Any]], step_key: str, field_key: str, *, default: bool
) -> bool:
    """`default` applies when the step/field is absent from the (already
    active-only) effective-form snapshot — a branch that deactivated the
    whole step, or a field key predating the running code's `defaults.py`.
    """
    field = _find_field(effective_form, step_key, field_key)
    if field is None:
        return default
    return bool(field["isRequired"])


def required_consent_keys(effective_form: list[dict[str, Any]]) -> set[str]:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and Recorded"
    — every field key the branch's Consent Agreement step marks required.
    """
    step = _find_step(effective_form, "consent_agreement")
    if step is None:
        return set()
    return {field["key"] for field in step["fields"] if field["isRequired"]}


def allowed_consent_keys(effective_form: list[dict[str, Any]]) -> set[str]:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and Recorded"
    — every field key defined on the branch's Consent Agreement step
    (required or not), the full set a creation request's `consents` payload
    is allowed to use. Mirrors `allowed_carried_item_keys` below: an empty
    set for a branch with no active Consent Agreement step, since nothing
    is a valid consent key in that case.
    """
    step = _find_step(effective_form, "consent_agreement")
    if step is None:
        return set()
    return {field["key"] for field in step["fields"]}


def allowed_carried_item_keys(effective_form: list[dict[str, Any]]) -> set[str]:
    """specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    Optional Structured Declarations" — the Carried Items step's `items`
    field `options`, or an empty set if that step/field isn't part of the
    branch's active configuration (nothing is a valid carried-item key for
    a branch with no active Carried Items step).
    """
    field = _find_field(effective_form, "carried_items", "items")
    if field is None or not field.get("options"):
        return set()
    return set(field["options"])
