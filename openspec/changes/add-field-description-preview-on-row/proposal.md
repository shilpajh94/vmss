## Why

An admin who sets a field's description in the Field Properties panel
(`form-builder-content-and-option-editing`) has no way to tell, from the
Active Form Fields list itself, which fields already have one set — the row
card shows the label, field-type badge, active/required state, and
edit/delete actions, but never the description. Reported directly: an admin
added a description to the Carried Items step's "Carried Items" field,
confirmed it saved (it shows correctly when the field is selected in the
Field Properties panel), but had no visual confirmation of that from the row
list itself and read it as the description "not being displayed."

## What Changes

- Each row in the Active Form Fields list (`SortableFieldRow.tsx`) that has
  a description set shows a short, truncated preview of it beneath the
  label/type-badge line — using the same expandable-text component
  (`ExpandableText`) already built for the visitor-facing renderer, so the
  truncation behavior (first sentence, "See more"/"See less") is visually
  and behaviorally consistent between the admin list and the public form,
  not a second, different preview implementation.
- A row with no description set renders exactly as it does today — no
  layout change, no placeholder text.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `form-builder`: adds a requirement that a field's description is visible
  on its row in the admin's Active Form Fields list, not only inside the
  Field Properties panel once that field is selected.

## Impact

- **Frontend (`VMMS_WEB`)**: `src/presentation/pages/admin-form-builder/
  Components/SortableFieldRow.tsx` — render `field.helpText` via the
  existing `ExpandableText` component
  (`src/presentation/components/ui/ExpandableText.tsx`, built in
  `form-builder-content-and-option-editing`) beneath the row's existing
  label/badge line.
- **Backend (`VMSS_API`)**: none — `field.helpText` already round-trips
  through the API; this is a pure display change to data already present
  on the client.
- **Tests**: none added — `VMMS_WEB` has no test framework (documented in
  `form-builder-content-and-option-editing`'s tasks.md); verified manually.
