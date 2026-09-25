## Why

The admin Field Properties panel (`FieldPropertiesPanel.tsx`) silently wipes
whatever an admin is typing — most visibly the Description textarea added in
`form-builder-content-and-option-editing`, but the same defect affects the
Label, Placeholder, Options editor, validation rules, and conditional-
visibility inputs too. Root cause: the step editor page auto-refreshes its
field list every 15 seconds in the background (`usePolling`, silent), and the
panel's `useEffect(() => { ...reset every local field... }, [field])` re-runs
on *any* new `field` object reference — including the one the silent
background refresh produces every 15 seconds for a field whose data hasn't
actually changed. An admin typing or pasting a longer description (or any
edit that takes more than ~15 seconds) has their in-progress, unsaved draft
overwritten back to the last-fetched server value mid-edit, and then can't
actually save the content they just entered — matching the reported bug
exactly ("typed or pasted content auto-removing, can't submit").

## What Changes

- `FieldPropertiesPanel` stops re-seeding its local draft state (label,
  placeholder, description, options, validation rules, visibility condition,
  width) on every background refresh of the same field. It only re-seeds when
  the admin has actually switched to editing a *different* field (i.e., the
  field's `id` changes), not merely when the containing page re-fetched the
  field list and produced a new object with identical values.
- No change to the panel's explicit "Reset" button, which still discards the
  current draft and reloads the latest server values for the selected field
  on demand.
- No change to the 15-second background refresh itself, or to any other
  page/component that relies on it (e.g. the field list rows, publish-state
  banner) — only to how the properties panel decides whether to treat an
  incoming `field` prop as "still the same field being edited" vs. "a
  different field was selected."

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `form-builder`: the two requirements added by
  `form-builder-content-and-option-editing` — "An Admin Can Update an
  Existing Field's Description" and "An Admin Can Edit an Existing
  Option-Bearing Field's Options" — gain a scenario each covering that an
  in-progress, unsaved edit survives a background refresh of the same field's
  data, since the current implementation violates that expectation.

## Impact

- **Frontend (`VMMS_WEB`)**: `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx`
  — narrow the `useEffect` (and, if needed, the initial `useState` seeding)
  that re-syncs local draft state from the `field` prop so it keys off
  `field.id` rather than the `field` object reference.
- **Backend (`VMSS_API`)**: none — this is a frontend state-management bug,
  not a data or API contract issue.
- **Tests**: none added — `VMMS_WEB` has no test framework (documented in
  `form-builder-content-and-option-editing`'s tasks.md); this fix will be
  verified manually against the reported repro (open a field, type/paste a
  multi-sentence description, wait past 15 seconds, confirm it's still there
  and saves correctly).
