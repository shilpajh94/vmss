## Why

In the admin Form Builder step editor, clicking a field's Edit (pencil) button
appears to do nothing: the "Field Properties" panel opens below the field list
(stacked under it on narrower screens, and at the top of a column that scrolls
out of view on wide screens), outside the visible area of the scroll region.
Admins can't see that the edit panel opened.

## What Changes

- When an admin explicitly selects a field to edit (Edit pencil or the field
  row's label), the step editor scrolls the Field Properties panel into view
  automatically.
- The automatic initial selection when a step loads does NOT scroll the page.
- If the panel is already fully visible, no scroll movement occurs.

## Capabilities

### New Capabilities

### Modified Capabilities
- `admin-form-builder`: adds a requirement that opening a field's edit panel brings the panel into view.

## Impact

- `src/presentation/pages/admin-form-builder/admin-form-builder-step-editor.tsx`
- `src/presentation/pages/admin-form-builder/hooks/use-admin-form-builder-step-editor.ts`
- Presentation-only; no API, schema, or dependency changes.
