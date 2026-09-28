"""Dynamic, branch-configured validation consulted by
`invitations/service.py::create_invitation` after `InvitationCreate`'s
Pydantic (structural) validation — see
`openspec/changes/form-builder/design.md` Decision 5. Works off the
resolved effective-form snapshot
(`form_builder/service.py::resolve_effective_form`), a plain JSON-shaped
list of step dicts, not the database directly.
"""

from typing import Any

from fastapi import HTTPException, status


def _find_step(effective_form: list[dict[str, Any]], step_key: str) -> dict[str, Any] | None:
    return next((step for step in effective_form if step["key"] == step_key), None)


def _find_field(
    effective_form: list[dict[str, Any]], step_key: str, field_key: str
) -> dict[str, Any] | None:
    step = _find_step(effective_form, step_key)
    if step is None:
        return None
    return next((field for field in step["fields"] if field["key"] == field_key), None)


def _find_group(
    effective_form: list[dict[str, Any]], step_key: str, group_key: str
) -> dict[str, Any] | None:
    step = _find_step(effective_form, step_key)
    if step is None:
        return None
    return next((group for group in step.get("groups", []) if group["key"] == group_key), None)


def validate_group_instance_count(
    group: dict[str, Any] | None, count: int, *, scope: str, skip_minimum: bool = False
) -> None:
    """specs/form-builder/spec.md "A Field Group May Be Marked Repeatable
    With a Configurable Instance Range" — enforces the same min/max check
    for Vehicle Info's group, Visitor Info's group (called only where its
    range is meaningful — see callers), and any admin-defined custom group.
    A missing or non-repeatable group has nothing to enforce. `skip_minimum`
    is set by a caller that has determined the group is currently hidden
    (specs/invitations/spec.md "A Hidden Custom Field Group's Fields Are
    Not Required At Submission") — a visitor who was never shown the group
    cannot be expected to have met its floor, but its ceiling still applies
    if instances were submitted anyway.
    """
    if group is None or not group.get("isRepeatable"):
        return
    min_instances = group.get("minInstances") or 0
    max_instances = group.get("maxInstances")
    if not skip_minimum and count < min_instances:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{scope} requires at least {min_instances} instance(s) of '{group['name']}'",
        )
    if max_instances is not None and count > max_instances:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{scope} allows at most {max_instances} instance(s) of '{group['name']}'",
        )


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


def required_consent_field_ids(effective_form: list[dict[str, Any]]) -> set[str]:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and Recorded"
    (restructure-walkin-payload-by-field-id) — every field id the branch's
    Consent Agreement step marks required. Consent fields are referenced by
    id, never by key/label, the same as any other admin-authored EAV
    answer.
    """
    step = _find_step(effective_form, "consent_agreement")
    if step is None:
        return set()
    return {field["id"] for field in step["fields"] if field["isRequired"]}


def allowed_consent_field_ids(effective_form: list[dict[str, Any]]) -> set[str]:
    """specs/invitations/spec.md (delta) "Consent Is Mandatory and Recorded"
    — every field id defined on the branch's Consent Agreement step
    (required or not), the full set a creation request's `consents` payload
    is allowed to reference. Mirrors `allowed_carried_item_keys` below: an
    empty set for a branch with no active Consent Agreement step, since
    nothing is a valid consent field id in that case. A `fieldId` belonging
    to a different branch's/tenant's form is never in this set either,
    since `effective_form` only ever reflects the resolved branch's own
    published configuration — so it's rejected the same way an unknown id
    is, with no special-case code needed for "wrong branch" versus
    "doesn't exist at all".
    """
    step = _find_step(effective_form, "consent_agreement")
    if step is None:
        return set()
    return {field["id"] for field in step["fields"]}


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


def _find_field_by_key(
    effective_form: list[dict[str, Any]], field_key: str
) -> dict[str, Any] | None:
    """Unlike `_find_field`, not scoped to one step — safe because a field
    key is unique across a branch's entire active form (specs/form-builder/
    spec.md "A Custom Field's Key Is Unique Across a Branch's Entire Active
    Form"), so every caller here can look a system field up by key alone.
    """
    for step in effective_form:
        field = next((f for f in step["fields"] if f["key"] == field_key), None)
        if field is not None:
            return field
    return None


_OPTION_BEARING_FIELD_TYPES = frozenset({"dropdown_select", "checkbox_list", "radio_button"})


def allowed_options_for_system_field(
    effective_form: list[dict[str, Any]], field_key: str
) -> list[str] | None:
    """specs/invitations/spec.md (delta) "A Retyped System Field's
    Submitted Value Is Validated Against Its Currently Configured Type"
    (make-system-field-types-editable) — generalizes what were
    `allowed_id_proof_types`/`allowed_vehicle_types` to every system field
    Form Builder allows to be retyped.

    Three distinct outcomes, not two:
    - The field isn't part of the branch's active configuration at all:
      `[]` — nothing is a valid value (matches the pre-existing behavior
      for a deactivated/absent `id_proof_type`/`vehicle_type`).
    - The field is active but its *currently configured* type isn't
      option-bearing (`dropdown_select`/`checkbox_list`/`radio_button`) — e.g. an admin
      retyped "Purpose of Visit" back to plain `text`: `None` — no options
      constraint applies; the caller should fall back to ordinary
      free-text validation instead of rejecting every value.
    - The field is active and option-bearing: its currently published
      `options` list (possibly empty, though publish validation prevents
      that for any field not exempted via `_EXTERNALLY_CATALOGED_FIELD_KEYS`).
    """
    field = _find_field_by_key(effective_form, field_key)
    if field is None:
        return []
    if field["fieldType"] not in _OPTION_BEARING_FIELD_TYPES:
        return None
    return list(field.get("options") or [])


def allowed_id_proof_types(effective_form: list[dict[str, Any]]) -> set[str] | None:
    """Thin wrapper over `allowed_options_for_system_field` — see
    specs/invitations/spec.md (delta) "Every Visitor Has a Reachable
    Contact and a Validated ID Proof". `None` means the field is currently
    configured as a non-option-bearing type: the caller should skip the
    allow-list check entirely rather than treat it as "nothing is valid".
    """
    options = allowed_options_for_system_field(effective_form, "id_proof_type")
    return None if options is None else set(options)


def vehicle_info_group(effective_form: list[dict[str, Any]]) -> dict[str, Any] | None:
    """specs/form-builder/spec.md "Vehicle Info and Visitor Info Are Seeded
    as Locked, Repeatable Groups" — the seeded "vehicles" group on Vehicle
    Info, or `None` if the branch's active configuration has no such group
    (e.g. Vehicle Info is deactivated).
    """
    return _find_group(effective_form, "vehicle_info", "vehicles")


def visitor_info_group(effective_form: list[dict[str, Any]]) -> dict[str, Any] | None:
    """specs/form-builder/spec.md "Vehicle Info and Visitor Info Are Seeded
    as Locked, Repeatable Groups" — the seeded "visitors" group on Visitor
    Info, whose `maxInstances` is the sole enforcement point for the
    group-registration visitor-count cap (add-repeatable-field-groups,
    revised Decision 5) — or `None` if the branch's active configuration
    has no such group (e.g. Visitor Info is deactivated, though it's a
    locked step and can't be in practice).
    """
    return _find_group(effective_form, "visitor_info", "visitors")


def is_group_visible(group: dict[str, Any], values: dict[str, Any]) -> bool:
    """specs/form-builder/spec.md "A Field Group May Declare Conditional
    Visibility" — evaluates the group's `visibilityCondition` against the
    values map for the scope its fields are answered at (the same map
    `validate_custom_field_values` validates that scope's fields against).
    A group with no condition is always visible.
    """
    condition = group.get("visibilityCondition")
    if condition is None:
        return True
    actual_value = values.get(condition["fieldKey"])
    matches = actual_value == condition["value"]
    return matches if condition["operator"] == "equals" else not matches


def allowed_vehicle_types(effective_form: list[dict[str, Any]]) -> set[str] | None:
    """Thin wrapper over `allowed_options_for_system_field` — see
    specs/invitations/spec.md (delta) "Carried Items and Vehicles Are
    Optional Structured Declarations". `None` means the field is currently
    configured as a non-option-bearing type: the caller should skip the
    allow-list check entirely rather than treat it as "nothing is valid".
    """
    options = allowed_options_for_system_field(effective_form, "vehicle_type")
    return None if options is None else set(options)


# --- Admin-authored custom fields (add-generic-custom-field-support) -------
#
# `isSystem` is what distinguishes a step's seeded fields (full name, email,
# category, purpose, the Carried Items `items` field, the Vehicle Info
# `license_plate` field, ...) — already handled by their own dedicated typed
# columns/checks above — from an admin-authored field added on top of them,
# whose answer is captured generically via `customFieldValues` instead. This
# split works uniformly for every step, including a custom step (every field
# on it is non-system) and Visitor Info/Visit Details (only their seeded
# fields are system).


def custom_fields_for_step(
    effective_form: list[dict[str, Any]], step_key: str
) -> list[dict[str, Any]]:
    """Every admin-authored (non-system) field on one active step whose
    answer belongs in that step's per-instance `customFieldValues` map —
    i.e. every such field except one assigned to an admin-defined
    (non-system) field group, whose answer is instead captured per-instance
    through `groupValues` (add-repeatable-field-groups), via
    `custom_groups_for_invitation_scope`.

    A field assigned to a *system* group (the seeded "vehicles"/"visitors"
    group on Vehicle Info/Visitor Info) is deliberately **included** here,
    not excluded: `custom_groups_for_invitation_scope`/`custom_groups_for_step`
    never surface a system group (their cardinality is the `vehicles`/
    `visitors` payload lists' own length, not a `groupValues` entry), so an
    admin-authored field an admin attaches to one of those system groups has
    no `groupValues` home to be captured through — its only route is this
    step's ordinary per-visitor/per-vehicle `customFieldValues` map, the same
    as an ungrouped field. Excluding it here as well as from every
    `groupValues` mechanism would silently orphan it: creatable in Form
    Builder, but never validated or collected anywhere.
    """
    step = _find_step(effective_form, step_key)
    if step is None:
        return []
    non_system_group_ids = {
        group["id"] for group in step.get("groups", []) if not group["isSystem"]
    }
    return [
        field
        for field in step["fields"]
        if not field["isSystem"] and field.get("groupId") not in non_system_group_ids
    ]


_NON_GENERIC_SCOPE_STEP_KEYS = ("visitor_info", "vehicle_info", "consent_agreement")
"""Steps excluded from `custom_fields_for_invitation_scope` because every
ungrouped field they carry — including an admin-authored one — is already
captured by a step-specific mechanism, not the generic `customFieldValues`
map: Visitor Info/Vehicle Info fields are per-visitor/per-vehicle (see
`custom_fields_for_step`), and *every* Consent Agreement field (system or
not) has always flowed through `consents`/`allowed_consent_keys`/
`required_consent_keys` above — that's the step's own generic mechanism,
predating this module's custom-field support, and folding its fields into
`customFieldValues` too would require the same key in two payload maps at
once. A *grouped* field on Visitor Info/Vehicle Info is unaffected by this
set — see `custom_groups_for_invitation_scope`'s own, narrower exclusion."""

_NO_GENERIC_GROUP_STEP_KEYS = ("consent_agreement",)
"""Steps excluded from `custom_groups_for_invitation_scope` — narrower than
`_NON_GENERIC_SCOPE_STEP_KEYS` above: Consent Agreement has no notion of a
repeatable group (consent is answered once, through `consents`), but
Visitor Info/Vehicle Info do — see `custom_fields_for_step`."""


def custom_fields_for_invitation_scope(
    effective_form: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Every admin-authored field whose answer is captured once per
    invitation via the generic `customFieldValues` map — every active step
    except the ones in `_NON_GENERIC_SCOPE_STEP_KEYS`
    (`add-generic-custom-field-support/design.md` Decision 1/2). Covers
    Visit Details, Carried Items (beyond its own `items` field), and any
    custom step. Excludes a field assigned to a field group
    (`field["groupId"] is not None`) — that field's answer is captured
    per-instance through `groupValues` instead
    (add-repeatable-field-groups); including it here too would validate it
    twice, once as a flat invitation-level answer and once per group
    instance, rejecting a submission that only ever answered it the
    group's way.
    """
    return [
        field
        for step in effective_form
        if step["key"] not in _NON_GENERIC_SCOPE_STEP_KEYS
        for field in step["fields"]
        if not field["isSystem"] and field.get("groupId") is None
    ]


def custom_groups_for_invitation_scope(
    effective_form: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Every *admin-defined* (non-system) field group defined on a step
    other than Consent Agreement (`_NO_GENERIC_GROUP_STEP_KEYS`), whose
    instances are submitted via the invitation payload's `groups` array,
    referenced by group id (specs/invitations/spec.md (delta) "An
    Admin-Defined Repeatable Group's Answers Are Accepted as an Array of
    Per-Instance Values" — restructure-walkin-payload-by-field-id).
    Excludes the seeded system groups ("vehicles" on Vehicle Info,
    "visitors" on Visitor Info) even though those live on steps this
    function otherwise covers — their cardinality is the `vehicles`/
    `visitors` payload lists' own length, validated separately by
    `vehicle_info_group`/`visitor_info_group`, not by a submitted `groups`
    entry (which they never have one of). Each returned group dict is
    augmented with a `"fields"` list — that group's own field definitions,
    resolved by the field ids it references — so a caller can validate one
    instance's values with `validate_custom_field_values` directly.
    """
    groups: list[dict[str, Any]] = []
    for step in effective_form:
        if step["key"] in _NO_GENERIC_GROUP_STEP_KEYS:
            continue
        fields_by_id = {field["id"]: field for field in step["fields"]}
        for group in step.get("groups", []):
            if group["isSystem"]:
                continue
            group_fields = [
                fields_by_id[fid] for fid in group.get("fieldIds", []) if fid in fields_by_id
            ]
            groups.append({**group, "fields": group_fields})
    return groups


def custom_groups_for_step(
    effective_form: list[dict[str, Any]], step_key: str
) -> dict[str, dict[str, Any]]:
    """Every admin-defined (non-system) field group on one active step,
    keyed by group id — used by a caller that needs to know which `groups`
    entries "belong" to a specific step (e.g. `invitations/router.py`
    synthesizing a visitor-shaped entry from a Visitor Info group's
    submitted instances), where `custom_groups_for_invitation_scope`'s
    branch-wide, presentation-agnostic list isn't scoped narrowly enough.
    Each returned group dict is augmented with a `"fields"` list the same
    way `custom_groups_for_invitation_scope` augments its groups, so a
    caller can inspect a member field's `fieldType` (e.g. to pick out an
    `email`/`phone`-typed field for a visitor-shaped presentation) and its
    `id` for indexing into an id-keyed instance map.
    """
    step = _find_step(effective_form, step_key)
    if step is None:
        return {}
    fields_by_id = {field["id"]: field for field in step["fields"]}
    return {
        group["id"]: {
            **group,
            "fields": [
                fields_by_id[fid] for fid in group.get("fieldIds", []) if fid in fields_by_id
            ],
        }
        for group in step.get("groups", [])
        if not group["isSystem"]
    }


def _field_label(field: dict[str, Any]) -> str:
    """Human-readable identifier for an error message — a raw `fieldId`
    (UUID) means nothing to whoever reads the rejection, so messages use
    the field's current `label` instead, falling back to its `id` only if
    a label is somehow blank."""
    return field.get("label") or field["id"]


def _validate_value_against_field(field: dict[str, Any], value: Any) -> None:
    field_type = field["fieldType"]
    options = field.get("options")
    label = _field_label(field)
    if field_type == "checkbox_list" and options:
        candidates = value if isinstance(value, list) else [value]
        if not set(candidates) <= set(options):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid option(s) for custom field '{label}'",
            )
    elif (
        field_type in ("dropdown_select", "radio_button") and options and value not in options
    ) or (
        field_type == "toggle_switch"
        and options
        and not isinstance(value, bool)
        and value not in options
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid option for custom field '{label}'",
        )

    rules = field.get("validationRules") or {}
    if isinstance(value, str):
        min_length, max_length = rules.get("minLength"), rules.get("maxLength")
        if min_length is not None and len(value) < min_length:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Custom field '{label}' is shorter than its minimum length",
            )
        if max_length is not None and len(value) > max_length:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Custom field '{label}' exceeds its maximum length",
            )
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        min_value, max_value = rules.get("minValue"), rules.get("maxValue")
        if min_value is not None and value < min_value:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Custom field '{label}' is below its minimum value",
            )
        if max_value is not None and value > max_value:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Custom field '{label}' exceeds its maximum value",
            )


def validate_custom_field_values(
    fields: list[dict[str, Any]],
    values: dict[str, Any],
    *,
    scope: str,
    skip_required: bool = False,
) -> None:
    """specs/invitations/spec.md (delta) "Invitation Creation Captures
    Admin-Defined Custom Field Answers" (restructure-walkin-payload-by-
    field-id) — `fields` is the admin-authored field set for one scope
    (`custom_fields_for_step`/`custom_fields_for_invitation_scope`),
    `values` the caller-supplied `{str(fieldId): value}` map for that same
    scope (`invitations/schemas.py::_custom_fields_to_dict`'s output) —
    never re-derived from or matched against a field's `key`. `scope` is
    only used to make a rejection's error message identify which visitor/
    vehicle/invitation-level answer set it came from. `skip_required` is set
    by a caller that has already determined the fields' owning group is
    currently hidden (specs/form-builder/spec.md "A Hidden Field Group
    Skips Required-Field Validation For Its Fields") — a supplied value is
    still validated even when its requiredness check is skipped.

    A `fieldId` that doesn't resolve against `fields` — because it's
    unknown, inactive, or belongs to a different branch/tenant's form
    entirely (`fields` only ever reflects the resolved branch's own
    effective form) — is rejected identically: there is no distinct code
    path for "wrong branch" versus "doesn't exist", by design (design.md
    Decision 5).
    """
    fields_by_id = {field["id"]: field for field in fields}
    unknown_ids = set(values) - set(fields_by_id)
    if unknown_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown custom field id(s) for {scope}: {', '.join(sorted(unknown_ids))}",
        )
    if not skip_required:
        missing_required = {field["id"] for field in fields if field["isRequired"]} - set(values)
        if missing_required:
            missing_labels = sorted(_field_label(fields_by_id[fid]) for fid in missing_required)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Missing required custom field(s) for {scope}: {', '.join(missing_labels)}"
                ),
            )
    for field_id, value in values.items():
        _validate_value_against_field(fields_by_id[field_id], value)
