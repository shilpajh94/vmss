## Context

See proposal.md - Why. This is a small, single-repo, single-capability change entirely inside `admin-form-builder`'s existing surfaces. Current code (confirmed by reading the source, not inferred):

- `FormFieldTypeSchema` (`src/domain/entities/form-builder-schema.ts:5-21`) is the 15-value wire enum, all snake_case (`dropdown_select`, `checkbox_list`, `toggle_switch`, ...). It is shared, unmodified, by both the admin-editor (`FormFieldGroupOutSchema`/`FormStepOutSchema`) and published-snapshot (`EffectiveFormStepSchema`) shapes.
- `src/presentation/pages/admin-form-builder/field-type-catalog.ts` is the single source of truth for the "Select Field Type" picker: `FIELD_TYPE_CATALOG` (tile list, consumed by `AddFieldModal.tsx` and `FieldPropertiesPanel.tsx`'s type dropdown) and `OPTION_REQUIRED_FIELD_TYPES` (currently `['dropdown_select', 'checkbox_list']`, consumed by both the create-time gate in `AddFieldModal.tsx` and `FieldPropertiesPanel.tsx`'s `optionsEditorIsShown`).
- `dynamic_table`, `rich_text_block`, `signature_pad` already have **no** visitor-facing renderer branch in `DynamicField.tsx` — they fall through to a generic "isn't supported inline yet" message (lines 143-147). Removing them from the picker is the entire scope of their removal; nothing downstream needs a compatibility shim.
- `FieldPropertiesPanel.tsx:42-45`'s `optionsEditorIsShown` treats `toggle_switch` as a special case: the options editor shows only if the field's *last-saved* `options` is non-null, independent of `OPTION_REQUIRED_FIELD_TYPES`. `radio_button` does not need this special case — like `dropdown_select`/`checkbox_list`, it always requires options, so a plain `OPTION_REQUIRED_FIELD_TYPES` entry is sufficient.
- No client-side non-empty-options check exists on update today (`FieldPropertiesPanel.tsx`'s `save()` relies on the backend 422 plus a substring match on `"options"` in the error message to revert the draft) — only `AddFieldModal.tsx` gates at create time. `radio_button` inherits both behaviors automatically once added to `OPTION_REQUIRED_FIELD_TYPES`; no new validation code is needed.

## Goals / Non-Goals

**Goals:**
- Keep the admin picker in sync with what the backend API will actually accept, so no admin action produces an avoidable 422.
- Give `checkbox_single` and `radio_button` the same level of support (picker tile, options-editor gating, visitor-facing rendering) that `dropdown_select`/`checkbox_list`/`toggle_switch` already have.

**Non-Goals:**
- No backend/API changes (already shipped and archived on VMSS_API's side).
- No migration of previously-submitted invitation data — a submitted answer for a since-removed type (if any exist) is read-only wire data and isn't touched; `VisitorInfoModal.tsx`'s generic custom-field renderer (unrelated to `DynamicField.tsx`) formats it from its raw value/field metadata regardless of `fieldType`, so nothing breaks there either.
- No change to `format-dynamic-field-value.ts` — confirmed it dispatches on the answer's runtime shape (boolean/array/object/string + `field.options` presence), not on `fieldType` literals, so a `checkbox_single` boolean and a `radio_button` string both already hit an existing branch correctly.

## Decisions

**1. Wire-format casing: snake_case (`checkbox_single`, `radio_button`), not camelCase.**
The task description's camelCase (`checkboxSingle`, `radioButton`) is prose styling, not the real payload shape — confirmed by user: the backend enum stays snake_case, matching all 13 untouched existing values. Decided rather than left open, since guessing wrong here means every field of the new types 422s in production.

**2. `checkbox_single` reuses the existing option-free-`toggle_switch` rendering pattern.**
`DynamicField.tsx:73-81` already renders a `toggle_switch` with no options as a single boolean `Checkbox`. `checkbox_single` is semantically identical (single boolean, no options) — same value shape, same control. Rather than introduce a new visual pattern, the new `checkbox_single` branch mirrors this one exactly (same `Checkbox` component, same `DynamicFieldValue` boolean shape), keeping the two boolean-toggle field types visually consistent for visitors.
Alternative considered: give `checkbox_single` its own distinct styling to differentiate it from `toggle_switch` in the visitor form. Rejected — the proposal's own framing ("no options needed, same shape as an option-free toggle_switch") and the existing codebase's `DynamicFieldValue` type (`string | boolean | string[] | DynamicFieldFileValue | undefined`) already treat "boolean, no options" as one case; splitting the rendering would be a cosmetic decision with no behavior difference, out of scope here.

**3. `radio_button` gets its own renderer branch, not a reuse of `dropdown_select`'s `SelectField`.**
The proposal is explicit that `radio_button` must render as radio buttons, not a dropdown, even though the underlying answer shape (a single string chosen from `field.options`) matches `dropdown_select` exactly. The new branch binds a native radio-input group (one input per `field.options` entry, shared `name` per field so selection is mutually exclusive) to the same string value `dropdown_select`'s `SelectField` branch already uses — no new `DynamicFieldValue` variant needed.
Alternative considered: add a `variant: 'dropdown' | 'radio'` flag to a shared component. Rejected as unnecessary abstraction for two call sites with already-divergent markup (a `<select>` vs. a set of `<input type="radio">`s) — see repo-wide guidance against introducing abstractions beyond what's needed today.

**4. `radio_button` joins `OPTION_REQUIRED_FIELD_TYPES`; `checkbox_single` does not.**
This one array drives the create-time gate (`AddFieldModal.tsx`), the properties-panel options editor visibility (`FieldPropertiesPanel.tsx`'s `optionsEditorIsShown`, for the non-`toggle_switch` branch), and (implicitly, since it's what the panel submits) the update-time 422/revert path. Adding `radio_button` here is sufficient to get all three behaviors for free, matching how `dropdown_select`/`checkbox_list` already work — no new code path needed beyond the catalog/constant edits themselves.

**5. Icon import cleanup is a checked step, not an assumption.**
`field-type-catalog.ts` imports `GridIcon`, `FileTextIcon`, `PenToolIcon` for the three removed tiles. `GridIcon` is also imported and used elsewhere (`FieldPropertiesPanel.tsx:5`, for an unrelated drag handle) — tasks.md must verify each icon's other usages individually before removing its import from `field-type-catalog.ts`, rather than blanket-deleting all three imports.

**6. The Field Properties type dropdown must keep showing an already-existing field's current type, even after that type leaves the catalog.**
Confirmed by reading `FieldPropertiesPanel.tsx:282-297`: when the type selector isn't disabled (`fieldTypeDisabled` false), its `options` come solely from `FIELD_TYPE_CATALOG.map(...)`; when disabled, it falls back to a single `{ value: fieldType, label: fieldTypeLabel(fieldType) }` entry for the field's own current type. Once `dynamic_table`/`rich_text_block`/`signature_pad` are removed from `FIELD_TYPE_CATALOG`, any pre-existing field still on one of those types (should one exist) would render a `<select>` whose `value` matches none of its `options` — an inconsistent, effectively-broken control. Fix: the non-disabled branch's `options` list must include the field's current type (via `fieldTypeLabel`) when it isn't already present in `FIELD_TYPE_CATALOG`, appended so it doesn't reorder the normal catalog tiles, same idea as the disabled branch already does unconditionally. This doesn't let an admin newly *choose* a removed type (it's not offered anywhere else, e.g. `AddFieldModal.tsx`'s grid), it only keeps an already-set one visible/selectable-away-from.

## Risks / Trade-offs

- **[Casing mismatch]** → Mitigated by Decision 1 confirmed with the user; if it later turns out the backend did use camelCase for the two new values, the fix is a one-line change to the two new enum entries (no architecture change), since decision 1 isolates the choice to `form-builder-schema.ts` and the two new catalog entries.
- **[No fields of the removed types are known to exist yet]** → The task description states these types "never had capture UI, validation, or rendering," suggesting no admin could have meaningfully used them; Decision 6's fix is cheap defensive handling for the case that one was created anyway, not a sign real data is expected.

## Migration Plan

No data migration. Deploy as a normal frontend release; the backend change is already live. No rollback complexity beyond a standard revert (this frontend change doesn't touch persisted data).
