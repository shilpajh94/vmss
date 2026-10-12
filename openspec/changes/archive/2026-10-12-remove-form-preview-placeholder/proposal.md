## Why

The Form Builder page (`/admin/form-builder`) shows a "Form Preview" button
in its heading row that does nothing. It is hard-coded `disabled`, has no
click handler, and only says "Coming soon" in its hover tooltip, which most
admins never see. To an admin it looks like a broken control or a missing
permission, and it takes space from the two actions that do work, "Create
Registration Step" and "Publish Changes". No preview feature is planned in
this cycle, so the placeholder should go.

## What Changes

- Remove the disabled "Form Preview" button from the Form Builder page's
  heading row. The row keeps the workspace selector, "Create Registration
  Step", and "Publish Changes".
- Update the `admin-form-builder` spec so the fixed-heading and
  compact-create-action requirements no longer list "Form Preview" among
  the heading controls.
- Out of scope: building a real form preview. If one is wanted later, it
  gets its own change and adds the button back with working behaviour.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `admin-form-builder`: the heading-controls requirements drop "Form
  Preview". The page no longer shows a non-functional preview control.

## Impact

- Code: `src/presentation/pages/admin-form-builder/admin-form-builder.tsx`
  (one `<button>` removed). No hook, API, or route changes.
- Backend (`VMSS_API`): none.
- Tests: no existing test refers to the button, so none need updating.
