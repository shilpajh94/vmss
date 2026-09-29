## 1. Frontend: Explain the Disabled Field Type Control

- [x] 1.1 `FieldPropertiesPanel.tsx`: add a short line of helper text
      directly beneath the "Field Type" `SelectField` when `field.isSystem`
      is true (e.g. "This is a default system field, so its type can't be
      changed."), matching the existing helper-text style used for the
      Required/Active and Options-editor lock explanations elsewhere in
      this panel
- [x] 1.2 Confirm the text does not render when `!field.isSystem` (type is
      editable, no explanation needed)
- [x] 1.3 Confirm the text renders identically for a locked field and a
      toggleable-but-system field (e.g. "Full Name" vs. "ID Proof Type") —
      both have `isSystem: true`, so both show the same explanation

## 2. Manual Verification

- [ ] ~~2.1 Manual verification (no frontend test framework in this repo,
      pre-existing gap): confirm in a running instance that opening "ID
      Proof Type" (toggleable system field) and "Full Name" (locked
      system field) both show the new explanatory text under the disabled
      Field Type dropdown, and that opening an admin-authored custom field
      shows the type dropdown enabled with no such text~~ — deferred, same
      as every prior form-builder change: no browser tooling in this
      sandbox to drive `VMMS_WEB` against a running instance. The
      condition gating the new text (`field.isSystem`) is a single boolean
      already exercised by existing pytest coverage of the field-type
      immutability behavior it explains; `tsc -b` and `oxlint` both pass
      clean. Flagged to the user to spot-check visually before shipping.
