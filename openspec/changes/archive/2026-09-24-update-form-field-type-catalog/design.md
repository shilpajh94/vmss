## Context

`FormFieldType` (`src/vmss_api/form_builder/schemas.py`) is a flat
`StrEnum` consulted in three places: request validation on
`FormFieldCreate`/`FormFieldUpdate` (via `OPTION_REQUIRED_TYPES`), the
type-change re-validation in `service.py`'s field-update path, and
submission-time value validation in `validation.py::_validate_value_against_field`.
`dynamic_table`, `rich_text_block`, and `signature_pad` were added to the
enum but never wired into any of these three call sites — see proposal.md
Impact. See proposal.md - Why for the motivation.

## Goals / Non-Goals

**Goals:**
- Remove the three unused field types from the supported set.
- Add `checkbox_single` and `radio_button` with the minimum logic needed
  so they behave consistently with the field types they're closest to
  (`toggle_switch` and `dropdown_select`, respectively).

**Non-Goals:**
- No data migration: confirmed via repo-wide search that no persisted
  fixture, seed, or test references the three removed types, and
  `defaults.py` (the system-field seed catalog) doesn't use them either.
  If a tenant's database happens to hold a field row with one of these
  types (none do in dev/test data), that row simply becomes uneditable
  via `field_type` until an admin picks a new type — the same failure
  mode any enum-value removal has, not something this change needs to
  script a backfill for.
- No new UI concepts: `checkbox_single` and `radio_button` don't need new
  panel logic in the backend's Field Properties contract — they slot into
  the existing option-free / option-required branches.

## Decisions

- **`radio_button` joins `OPTION_REQUIRED_TYPES`, `checkbox_single`
  doesn't.** `OPTION_REQUIRED_TYPES` already exists specifically to
  distinguish "this type's value is meaningless without a declared option
  set" (`dropdown_select`, `checkbox_list`) from types that don't need
  one. `radio_button` is single-select-from-a-set, same as
  `dropdown_select` — it belongs in the set for the same reason.
  `checkbox_single` is a lone boolean, same as an option-free
  `toggle_switch` — it doesn't declare options at all, so it stays out.
  Alternative considered: giving `checkbox_single` an optional single
  "label override" via `options`; rejected as unnecessary — the field's
  existing `label`/`help_text` already cover that, and inventing a
  second use for `options` (a 1-item list) would need its own validation
  rule for no behavioral gain.
- **`_validate_value_against_field` grows one `elif` branch for
  `radio_button`, folded into the existing `dropdown_select` condition
  (same rule: value must be in `options` when `options` is set) rather
  than a new standalone branch.** Keeps the function's existing
  structure (`checkbox_list` branch, then a combined
  single-value-membership branch) instead of adding a third parallel
  branch for logic that's identical to one already there.
- **`checkbox_single` gets no new branch in `_validate_value_against_field`.**
  It follows the same path an option-free `toggle_switch` follows today
  (no options declared → no membership check runs) — see proposal.md
  Impact. Introducing stricter boolean-type enforcement for
  `checkbox_single` alone, when `toggle_switch` has none, would be a new
  validation behavior this change doesn't need and the spec doesn't
  require.
- **No new `_TYPE_LOCKED_SYSTEM_FIELD_KEYS` entries.** Neither new type
  is a system field's type; the existing type-change gating in
  `service.py` (`A System Field's Type Is Editable...`) is untouched.

## Risks / Trade-offs

- [Removing enum members is a breaking change for any external client
  that already sends `dynamicTable`/`richTextBlock`/`signaturePad` as a
  `fieldType`] → None of VMSS_API's own callers (admin portal, seed
  data, tests) use these values today per the repo-wide search in
  proposal.md Impact; document the removal in the PR description per
  `api-conventions.md` §2's breaking-change expectations since the React
  portal is a separate repo/release cadence.

## Migration Plan

- No Alembic migration: `field_type` is stored as a plain string column
  (enum validation happens at the Pydantic layer only), so no schema
  change is needed. Deploy is a single backend release; no phased
  rollout required given no known persisted rows use the removed types.
