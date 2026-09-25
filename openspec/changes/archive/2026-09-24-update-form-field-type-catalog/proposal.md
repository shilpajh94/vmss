## Why

Three field types in the "Select Field Type" catalog — Dynamic Table,
Signature Pad, and Rich Text Block — are not implemented beyond an enum
member: no capture UI, no submission-time validation, no rendering
behavior. Leaving them selectable lets an admin pick a type that silently
does nothing useful on a visitor-facing form. At the same time, admins
building a visitor registration form regularly need a plain single
checkbox (e.g. "I agree to the terms") and a mutually-exclusive
single-select rendered as radio buttons, and neither exists today —
`checkbox_list` only supports multi-select, and `dropdown_select` is the
only single-select option.

## What Changes

- **BREAKING**: Remove the `dynamic_table`, `rich_text_block`, and
  `signature_pad` field types from `FormFieldType`. Any existing field row
  persisted with one of these types is no longer a valid `field_type` for
  create/update requests.
- Add `checkbox_single`: a single boolean checkbox field (e.g. a consent/
  agreement checkbox), following the same option-free, boolean-value shape
  `toggle_switch` uses today — no `options` list required.
- Add `radio_button`: a single-select field rendered as mutually-exclusive
  radio buttons, functionally equivalent to `dropdown_select`'s
  single-value-from-a-set semantics — joins `OPTION_REQUIRED_TYPES`, so
  creation/update require a non-empty `options` list, and submitted values
  are validated against that list the same way `dropdown_select` values are.
- Field Properties panel behavior already generic across field types (type
  editability, options editing for option-bearing types, description
  rendering) extends to `checkbox_single` and `radio_button` with no new
  special-casing, and no longer offers the three removed types as
  selectable or resulting values.

## Capabilities

### Modified Capabilities
- `form-builder`: the supported field-type catalog changes — three unused
  types are removed, two new option-free/option-required types are added,
  and existing type-dependent requirements (options editing, submission
  validation, type-change re-validation) are extended to cover
  `radio_button` as an option-required type and `checkbox_single` as a
  boolean, option-free type.

## Impact

- `src/vmss_api/form_builder/schemas.py`: `FormFieldType` enum members
  added/removed; `OPTION_REQUIRED_TYPES` gains `radio_button`.
- `src/vmss_api/form_builder/validation.py`: `_validate_value_against_field`
  gains a `radio_button` branch (same rule as `dropdown_select`) and a
  `checkbox_single` branch (same rule as option-free `toggle_switch`,
  boolean value, no options).
- `src/vmss_api/form_builder/service.py`: type-change re-validation
  (`resulting_needs_options`, options-clearing-on-type-change) picks up
  `radio_button` automatically via `OPTION_REQUIRED_TYPES`; no separate
  code path needed for the three removed types since they carried no
  special-case logic.
- No stored field rows, migrations, or other capabilities (`invitations`,
  `registrations`) reference the removed types today, so this is a
  contained change to `form_builder`'s own field-type catalog and its
  test coverage in `src/vmss_api/form_builder/tests.py`.
