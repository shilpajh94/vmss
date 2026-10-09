## Why

`fix-field-type-editing-and-lock-ux` made an admin-authored field's type
editable, gated on `isSystem` (correctly — a toggleable system field like
"ID Proof Type" or "Additional Notes" is just as structurally load-bearing
as a locked one). But that field is *not* visually marked "Locked" in the
admin UI (no lock badge, its delete button still shows, its Required
checkbox is freely editable) — so an admin opening its Field Properties
panel sees an ordinary-looking field with a mysteriously disabled Field
Type dropdown and no explanation anywhere. This is exactly what prompted
the question this change answers: nothing in the UI ever says *why*.

## What Changes

- The Field Properties panel shows a short inline explanation directly
  under the Field Type control whenever it's disabled (`field.isSystem`),
  the same way the panel already explains the analogous Required/Active
  restriction and the Options-editor lock restriction — instead of a
  disabled control with no accompanying text.
- No behavior change: the field type is already correctly immutable for
  system fields (locked or toggleable) — this only makes the existing,
  correct restriction legible to the admin looking at it.

## Capabilities

### New Capabilities

(none — this continues refining the existing `form-builder` capability)

### Modified Capabilities

- `form-builder`: adds a requirement that the admin UI explain, in place,
  why a system field's Field Type control is disabled.

## Impact

- **Frontend (`VMMS_WEB`)**:
  - `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx` —
    add explanatory helper text beneath the Field Type `SelectField` when
    `field.isSystem` is true.
- **Backend**: none — this is a display-only change; the enforcement this
  explains already exists and is unchanged.
- **Tests**: frontend has no test framework in this repo (pre-existing,
  unchanged); no backend behavior changed, so no new backend tests are
  needed. Covered by manual verification, as with every prior form-builder
  UI-only change.
