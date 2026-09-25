## Why

Live use of the `static_text` field type and the Field Properties panel's
new Lock/Unlock control (`add-static-text-field-and-unlock-toggle`)
surfaced three gaps that change didn't cover:

1. The "Add New Custom Field" modal correctly hides the Required toggle for
   a `static_text` field, but the field list's own row (`SortableFieldRow`)
   renders an unconditional "Required" checkbox for every field regardless
   of type — so a saved `static_text` field still shows a meaningless (and,
   since the backend now rejects it, non-functional) Required checkbox in
   the step's field list.
2. A field's type has never been editable after creation — the Field
   Properties panel's "Field Type" selector is permanently disabled. That
   was fine while every editable property was type-agnostic, but there's no
   way today to fix a field created with the wrong type (e.g. `text`
   instead of `dropdown_select`) without deleting and recreating it, losing
   its key, order position, and any already-submitted answers' association.
3. The Lock/Unlock control added for locked fields reads as two phrases
   mashed together ("Locked — Unlock to Edit" / "Editing — Lock"), which is
   confusing as a single clickable button. It should read as one clear
   action label.

## What Changes

- `SortableFieldRow`'s "Required" checkbox no longer renders for a
  content-only field type (`static_text`, matching the same
  `CONTENT_ONLY_FIELD_TYPES` set the Add/Edit panels already use) — the row
  shows no Required control for that field, the same way the field
  properties panel and creation modal already omit it.
- An admin-authored (`isSystem: false`) field's type becomes editable from
  the Field Properties panel — changing it re-evaluates the same
  type-dependent constraints field creation already enforces (a
  newly-option-required type needs a non-empty options list; a field
  changed to `static_text` can't be required and needs body content) and
  clears stale `options` when the new type isn't option-bearing. A
  system-seeded field's type (locked or toggleable) stays fixed, matching
  the field type never being able to change for those — they're keyed into
  real invitation/registration code paths and columns
  (`org_structure`/`invitations`/`registrations`), not something a type
  switch can safely repoint.
- The Lock/Unlock control on a locked field becomes a single button
  labeled "Unlock to Edit" while locked, and "Lock" once the admin has
  unlocked it for editing — dropping the combined "Locked —"/"Editing —"
  prefixes from `add-static-text-field-and-unlock-toggle`'s first pass.

## Capabilities

### New Capabilities

(none — this continues refining the existing `form-builder` capability)

### Modified Capabilities

- `form-builder`: fixes the Required-checkbox-on-a-content-only-field
  display bug; adds field-type editability for admin-authored fields
  (a genuinely new requirement, not just a bug fix); simplifies the
  Lock/Unlock control's button text to a single, unambiguous label.

## Impact

- **Backend (`VMSS_API`)**:
  - `src/vmss_api/form_builder/schemas.py` — add `field_type:
    FormFieldType | None` to `FormFieldUpdate`.
  - `src/vmss_api/form_builder/service.py` — `update_field` rejects a
    `field_type` change on an `is_system` field; re-validates
    options/required/help_text against the *resulting* field type (current
    value for anything not included in this update, the new value for
    anything that is); clears `options` to `null` when the resulting type
    isn't option-bearing.
  - No database migration: `field_type` is already a plain `String(30)`
    column.
- **Frontend (`VMMS_WEB`)**:
  - `src/presentation/pages/admin-form-builder/Components/SortableFieldRow.tsx` —
    hide the Required checkbox for a content-only field type.
  - `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx` —
    Field Type selector becomes an editable dropdown (same catalog as
    "Add New Custom Field") when `!field.isSystem`; changing it updates
    which other controls the panel shows (Options editor,
    Placeholder/Required for `static_text`) the same way those already
    react to a field's original type; Lock/Unlock button text simplified to
    "Unlock to Edit"/"Lock".
  - `src/domain/entities/form-builder-schema.ts` — add `fieldType?:
    FormFieldType` to `FormFieldUpdateInput`.
- **Tests**: new backend `pytest` coverage for field-type-change validation
  (system field rejected, options required/cleared appropriately,
  `static_text` constraints re-checked on type change) and for the
  existing effective-form/publish pipeline reflecting a changed type.
  Frontend has no test framework in this repo (pre-existing, unchanged) —
  covered by manual verification as with every prior form-builder change.
