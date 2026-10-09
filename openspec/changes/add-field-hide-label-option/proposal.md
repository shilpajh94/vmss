## Why

The Form Builder API now supports a per-field `hideLabel: boolean` (see `openspec/changes/archive/add-field-hide-label-option/` in VMSS_API, once archived), returned on every field object (admin list/create/update responses and the public `GET /form-builder/effective` snapshot), defaulting to `false`. It lets an admin configure a field whose `label` is still required and still the field's accessible name, but shouldn't render as visible text — e.g. a single field on an otherwise self-explanatory step, or a field placed right next to explanatory static text that already states what it's for. Nothing on the frontend reads or sets this property yet, so admins have no way to use it even though the backend now supports it.

## What Changes

- Domain schema: add `hideLabel: boolean` to `FormFieldOutSchema`/`FormField` (used by both the admin-editor and published-snapshot shapes) and to `FormFieldCreateInput`/`FormFieldUpdateInput`.
- Admin Field Properties panel (`FieldPropertiesPanel.tsx`): add a "Hide Label" toggle (mirroring the existing `ToggleSwitch` pattern used for "Required Field"), sent as `hideLabel` in the `PATCH /form-builder/fields/{id}` body. Not exposed in `AddFieldModal.tsx` at creation time — this follows the same precedent already set by `width`, which is likewise edit-only and defaults server-side, not creation-time-settable.
- Visitor-facing renderer (`DynamicField.tsx` and the shared UI primitives it uses — `TextField`, `SelectField`, `TextareaField`, `FileUploadField`, `Checkbox`): when a field's `hideLabel` is `true`, the label text is visually hidden but stays in the DOM and programmatically associated with its control (via the existing `sr-only` + linked-`<label>` idiom already used elsewhere in this codebase, e.g. `admin-workflow-form.tsx`'s `labelClassName="sr-only"`), so it remains the control's accessible name for assistive technology. `static_text` fields are unaffected — a prior change already stopped rendering their `label` as a visible heading at all (see `DynamicField.tsx`'s `static_text` branch), so `hideLabel` is a no-op there.
- No validation behavior changes — a required field with `hideLabel: true` still enforces its required-value rule exactly as before; this is purely a rendering flag, confirmed by the backend reference.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-form-builder`: the Field Properties panel gains a "Hide Label" control, and a field's visitor-facing rendering respects `hideLabel` while preserving the label as the control's accessible name.

## Impact

- `src/domain/entities/form-builder-schema.ts` — `FormFieldOutSchema`/`FormField`, `FormFieldCreateInput`, `FormFieldUpdateInput`.
- `src/presentation/pages/admin-form-builder/Components/FieldPropertiesPanel.tsx` — new toggle + `save()` payload.
- `src/presentation/components/dynamic-fields/DynamicField.tsx` — thread `field.hideLabel` into each rendered control/heading.
- `src/presentation/components/ui/{TextField,SelectField,TextareaField,FileUploadField}.tsx` — the first three already accept a `labelClassName` override and need no change; `FileUploadField` needs the same `labelClassName` prop added, since it currently hardcodes its label's class.
- `src/presentation/components/ui/Checkbox.tsx` — needs a way to visually hide its inline `children` label while keeping it part of the associated `<label>` element.
- No change to `format-dynamic-field-value.ts`, validation logic, or any repository/use-case beyond passing the new field through (it already flows generically via `z.infer`/spread payloads, not field-by-field destructuring, in the places that matter).
