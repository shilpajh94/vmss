## Why

The Form Builder workspace dropdown lists "Tenant Default" twice. `SelectField`
always renders its own placeholder `<option value="">` (labelled by the
`placeholder` prop), and `admin-form-builder.tsx` *also* passes an explicit
`{ value: '__default__', label: 'Tenant Default' }` option — so the same choice
appears once as the placeholder and once as a real option. The two
"Conditional Visibility" dropdowns (field and group) have the identical pattern
and show "Always shown" twice. There it is also a functional bug: picking the
placeholder copy sets the value to `''`, which is not equal to the
`'__none__'` sentinel, so the UI treats "Always shown" as a real condition and
reveals the operator/value inputs.

## What Changes

- Form Builder workspace selector shows exactly one "Tenant Default" entry,
  followed by one entry per branch.
- Field and group "Show this field/group when:" selectors show exactly one
  "Always shown" entry, followed by the pickable fields.
- Selecting "Always shown" always clears the condition (hides the
  operator/value inputs and saves `visibilityCondition: null`), regardless of
  which DOM option the browser reports.
- No change to `SelectField`'s public API or to other callers
  (host-employee "All branches", kiosk "All" status filter), which already use
  the placeholder correctly without a duplicate option.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `admin-form-builder`: add requirements that the workspace selector and the
  conditional-visibility selectors list their "default/none" choice exactly
  once, and that choosing "Always shown" clears the condition.

## Impact

- `src/presentation/pages/admin-form-builder/admin-form-builder.tsx`
- `src/presentation/pages/admin-form-builder/hooks/use-admin-form-builder.ts`
  (`DEFAULT_WORKSPACE_VALUE`)
- `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx`
- `src/presentation/pages/admin-form-builder/Components/GroupCard.tsx`
- Web-only; no API change, no data migration.
