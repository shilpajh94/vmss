## Why

The form builder's "Add New Custom Field" and "Field Properties" panels let an
admin set a field's label, placeholder, required flag, and (at creation time
only) its options — but there is no way to attach admin-editable static
content to a field, or to change the options of a field after it's created.
Two concrete symptoms: the Consent Agreement step's "Terms & Conditions",
"Data Processing Consent", and "Safety Guidelines" toggles have no way to
carry their actual agreement text (it would have to be hardcoded into the
frontend per step), and the Carried Items step's checkbox options
("Laptop/Tablet", "Mobile Phone", "Food & Beverages", "Other", ...) can only
ever be set once at field creation — an admin who wants to add, remove, or
rename an option on that existing field has no UI to do it. The backend
(`FormField.help_text`, `FormField.options`) already supports both pieces of
data end-to-end via `FormFieldCreate`/`FormFieldUpdate`; the gap is entirely
in the admin UI (no input for it) and the visitor-facing renderer (nothing
renders `help_text` today, and no field type renders it with truncation).

## What Changes

- Admin "Add New Custom Field" modal gains a "Description" textarea (maps to
  the existing `help_text` field) so an admin can attach static explanatory
  text — e.g. the actual terms-and-conditions body — to any field at creation
  time, for any step.
- Admin "Field Properties" panel (editing an existing field) gains the same
  "Description" textarea, plus an "Options" editor (add/remove/reorder/rename
  option rows) for `checkbox_list`, `dropdown_select`, and optioned
  `toggle_switch` fields — closing the gap where an existing field's option
  list could only be set once, at creation, and never revisited. Both
  controls follow the same locked-field posture already used for
  label/placeholder: disabled (read-only) when `field.isLocked` is true,
  editable otherwise. Removing an option that a live visibility condition or
  in-flight submission references is out of scope for this change (see
  design.md Non-Goals).
- Visitor-facing form renderer (`DynamicField`) renders a field's description
  under its input, for every field type that has one, truncated to its first
  sentence with a "See more" / "See less" toggle — implemented as one new
  reusable expandable-text component, not a per-step special case. This is
  new UI; no equivalent truncation/expand component exists in the codebase
  today.
- No backend/API changes: `help_text` and `options` are already accepted end
  to end by `FormFieldCreate`/`FormFieldUpdate`/`FormFieldOut` and already
  render in `GET /form-builder/effective`. This change is admin-UI +
  visitor-UI only.

## Capabilities

### New Capabilities

(none — this extends the existing `form-builder` capability's admin-editing
and rendering behavior; it introduces no new domain capability of its own)

### Modified Capabilities

- `form-builder`: adds requirements that (1) a field's admin-editable
  description text must be settable at creation and update time through the
  admin UI, (2) an existing option-bearing field's option list must be
  editable (not just settable once at creation) through the admin UI subject
  to the same locked-field restriction as label/placeholder, and (3) the
  visitor-facing renderer must display a field's description, truncated to
  its first sentence with an expand/collapse control, for every field type
  and step uniformly.

## Impact

- **Frontend (`VMMS_WEB`)**:
  - `src/presentation/pages/admin-form-builder/Components/AddFieldModal.tsx` —
    new Description textarea, included in the `FormFieldCreateInput` payload.
  - `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx` —
    new Description textarea and new Options editor, both gated on
    `field.isLocked`; `onSave` payload extended to include `helpText` and
    `options`.
  - `src/presentation/components/dynamic-fields/DynamicField.tsx` — every
    branch renders the new expandable-description component beneath the
    field's input when `field.helpText` is set.
  - New shared component (exact path decided in design.md) implementing the
    truncate/expand-collapse behavior, reused by every field type.
- **Backend (`VMSS_API`)**: none — `form_builder/schemas.py`,
  `form_builder/service.py`, and `form_builder/router.py` already support
  `help_text` and `options` on both create and update; no migration, no new
  endpoint.
- **Tests**: new/updated frontend component tests for the two admin panels
  and the new expandable-description component; no backend test changes
  expected since no backend behavior changes.
