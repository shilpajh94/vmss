## Why

The backend's Form Builder API (`/form-builder/steps/*/fields`, create + update) has shipped a breaking change to its `fieldType` catalog (see `openspec/changes/archive/2026-09-24-update-form-field-type-catalog/` in VMSS_API): `dynamic_table`, `rich_text_block`, and `signature_pad` are no longer accepted (422 on create/update) and were never wired up for capture, validation, or visitor-facing rendering on either side anyway. Two new types, `checkbox_single` and `radio_button`, are now accepted. The frontend's "Select Field Type" picker still offers the three removed types as live tiles today, so an admin who picks one now gets a 422 instead of a saved field, and the two new types have no picker entry or visitor-facing renderer at all.

## What Changes

- **BREAKING**: Remove `dynamic_table`, `rich_text_block`, `signature_pad` from `FormFieldTypeSchema` (`src/domain/entities/form-builder-schema.ts`) and their tiles from the "Select Field Type" picker (`FIELD_TYPE_CATALOG` in `src/presentation/pages/admin-form-builder/field-type-catalog.ts`, used by both `AddFieldModal.tsx` and `FieldPropertiesPanel.tsx`'s field-type dropdown) — an admin can no longer select a type the API will reject. These three never had visitor-facing rendering (`DynamicField.tsx` already falls through to "isn't supported inline yet" for them) or admin-side capture/validation beyond the picker tile, so removing the tile has no other surface to update.
- Add `checkbox_single` (a single boolean checkbox, no options — same value shape as a `toggle_switch` with no options) and `radio_button` (mutually-exclusive single-select from a required non-empty `options` array, same semantics as `dropdown_select` but rendered as radio buttons) to `FormFieldTypeSchema`, the picker catalog, and `OPTION_REQUIRED_FIELD_TYPES` (for `radio_button` only — `checkbox_single` needs no options editor).
- Add visitor-facing rendering for both new types in `DynamicField.tsx`: `checkbox_single` reuses the existing single-`Checkbox` boolean pattern (currently used for an option-free `toggle_switch`); `radio_button` renders a radio-button group bound to `field.options`, mirroring `dropdown_select`'s `SelectField` branch but as radio inputs.
- Field Properties panel's options editor (add/remove/reorder) extends to cover `radio_button` the same way it already covers `dropdown_select`/`checkbox_list`, via `OPTION_REQUIRED_FIELD_TYPES`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-form-builder`: the set of `fieldType` values the "Select Field Type" picker offers and the Field Properties panel's options-editor gating change (3 removed, 2 added); visitor-facing rendering of a field answer gains two new type cases.

## Impact

- `src/domain/entities/form-builder-schema.ts` — `FormFieldTypeSchema` enum (wire contract shared with the backend; every existing 13 values are unaffected and keep their current snake_case wire format — see design.md for the casing decision).
- `src/presentation/pages/admin-form-builder/field-type-catalog.ts` — `FIELD_TYPE_CATALOG` tiles, `OPTION_REQUIRED_FIELD_TYPES`.
- `src/presentation/pages/admin-form-builder/Components/AddFieldModal.tsx`, `FieldPropertiesPanel.tsx` — consume the catalog/constant above; no bespoke per-type logic to change beyond what the catalog drives.
- `src/presentation/components/dynamic-fields/DynamicField.tsx` — visitor-facing renderer, new `checkbox_single`/`radio_button` branches.
- No backend/API contract changes on this side (VMSS_API already shipped and archived its change); no change to `format-dynamic-field-value.ts`, validation-rules UI, or any other consumer (confirmed via full-tree grep — see design.md).
- Any invitation submitted with a field of a removed type before this backend change remains readable (existing wire data isn't touched), but an admin can no longer create/edit a field of that type going forward.
