## Why

Admins configuring the Form Builder have two concrete gaps today. First,
there is no field type for pure admin-authored display content — e.g. a
company's actual Terms & Conditions or Safety Guidelines text — that
renders on the form with no visitor input attached (the closest existing
mechanism, a field's `helpText`, is always a caption bolted onto some other
field's input, never a standalone block). Second, the six-or-so mandatory
system fields seeded per step (Full Name, Email, Purpose of Visit, License
Plate, ...) are permanently locked: the admin UI disables their
label/placeholder/description/options inputs with no way to ever turn that
off, even though the backend already accepts those edits for a locked
field — only `isActive`/`isRequired` are actually blocked server-side. An
admin who needs to reword a mandatory field's label or retitle its options
has no path to do so today short of a direct API call.

## What Changes

- Add a new `static_text` field type: an admin authors a title (the
  field's `label`) and body content (the field's `description`/`helpText`)
  from the "Add New Custom Field" modal and Field Properties panel, the
  same as any other field type; it renders on the visitor/staff form as
  that title + body with no input control and collects no answer. It
  cannot be marked required (there is nothing to fill in).
- Add a Lock/Unlock control to the Field Properties panel for any
  `isLocked` field. Locked is still the default, matching today's
  behavior exactly. Clicking "Unlock to Edit" enables that field's Label,
  Placeholder, Description, and (if it is option-bearing) its Options
  editor for editing and saving. Required and Active stay fixed regardless
  of unlock state — a mandatory field's requiredness/visibility can't be
  turned off, since it backs a non-nullable database column — matching
  today's existing backend enforcement, which this change does not loosen.
  Re-locking (or reselecting a different field) discards any unsaved edits
  and returns the panel to its default disabled state.
- Verify (and cover with tests) that both the new field type's content and
  edits made through the unlock flow persist to the draft, publish into the
  branch's `FormConfigVersion` snapshot, and render identically on both the
  visitor self-registration wizard and the staff/walk-in registration
  wizard — they already share one config-resolution path and one set of
  rendering components, so this is a regression-safety check on the
  existing pipeline, not new plumbing.

Out of scope: per-type option-list editing for `dropdown_select`/
`checkbox_list` fields is already fully implemented (creation-time and
post-creation, via the Field Properties panel's Options editor) — no
changes needed there beyond making that same editor usable on a locked
field once unlocked, which the Lock/Unlock item above already covers.

## Capabilities

### New Capabilities

(none — this extends the existing `form-builder` capability)

### Modified Capabilities

- `form-builder`: adds the `static_text` field type and its
  content-authoring/rendering behavior; adds the lock/unlock affordance
  that lets an admin edit a locked field's label/placeholder/description/
  options while keeping its required/active state and field type fixed;
  updates the existing "locked field's description/options cannot be
  edited" scenarios to account for the new unlocked state; adds an
  explicit cross-surface (staff + visitor) rendering/persistence
  requirement.

## Impact

- **Backend (`VMSS_API`)**:
  - `src/vmss_api/form_builder/schemas.py` — add `static_text` to
    `FormFieldType`; reject `is_required=True` for a `static_text` field on
    both create and update; require non-empty `help_text` for a
    `static_text` field at creation.
  - `src/vmss_api/form_builder/service.py` — enforce the create/update
    `static_text`-is-never-required rule at the point `FormFieldUpdate`
    doesn't carry `field_type` (must check the existing row's type).
  - No database migration: `field_type` is a plain `String(30)` column, not
    a native Postgres enum, and no new column is needed — the new field
    type reuses `label`/`help_text` as title/body.
  - `docs/features/form_builder.md` — document the new field type and the
    unlock affordance.
- **Frontend (`VMMS_WEB`)**:
  - `src/domain/entities/form-builder-schema.ts` — add `static_text` to the
    `FormFieldTypeSchema` Zod enum.
  - `src/presentation/pages/admin-form-builder/field-type-catalog.ts` — add
    a catalog entry for `static_text`.
  - `src/presentation/pages/admin-form-builder/Components/AddFieldModal.tsx` —
    hide Placeholder/Required for `static_text`; adjust copy so Label reads
    as "title" and Description reads as the block's body.
  - `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx` —
    add the Lock/Unlock control; gate Label/Placeholder/Description/Options
    `disabled` state on `isLocked && !isUnlockedForEditing` instead of
    `isLocked` alone; hide Placeholder/Required for `static_text`.
  - `src/presentation/components/dynamic-fields/DynamicField.tsx` — add a
    `static_text` render branch (heading only; the existing
    `ExpandableText(helpText)` call the wrapper already makes for every
    field type becomes the body, unchanged).
- **Tests**: new backend `pytest` coverage in
  `src/vmss_api/form_builder/tests.py` (or its `tests/` package) for the
  `static_text` validation rules and for publish→effective-form parity
  across the staff and visitor submission paths. Frontend has no test
  framework in this repo today (pre-existing gap, not introduced by this
  change) — frontend behavior is covered by manual verification only, as
  in every prior form-builder change.
