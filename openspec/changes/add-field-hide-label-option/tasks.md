## 1. Domain schema

- [x] 1.1 In `src/domain/entities/form-builder-schema.ts`, add `hideLabel: z.boolean()` to `FormFieldOutSchema`.
- [x] 1.2 Add `hideLabel?: boolean` to `FormFieldUpdateInput`.
- [x] 1.3 Add `hideLabel?: boolean` to `FormFieldCreateInput` per the backend contract, even though `AddFieldModal.tsx` won't send it yet (design.md Non-Goals) — keeps the type accurate for any future caller.

## 2. Shared UI primitives

- [x] 2.1 Add a `labelClassName?: string` prop to `FileUploadField` (`src/presentation/components/ui/FileUploadField.tsx`), applied to its `<label htmlFor={inputId}>` the same way `TextField`/`SelectField`/`TextareaField` already do (default to the existing hardcoded class when not passed).
- [x] 2.2 Add a `hideLabel?: boolean` prop to `Checkbox` (`src/presentation/components/ui/Checkbox.tsx`) that wraps `<span>{children}</span>` in `sr-only` when true, leaving the `<input>` inside the same `<label>` either way.
- [x] 2.3 Confirm `TextField`/`SelectField`/`TextareaField` need no changes — they already accept `labelClassName`.

## 3. Visitor-facing renderer

- [x] 3.1 In `DynamicField.tsx`'s `renderControl`, for the `checkbox_single`/option-free-`toggle_switch` branch, pass `hideLabel={field.hideLabel}` to `Checkbox`.
- [x] 3.2 For the `checkbox_list`/`toggle_switch`-with-options branch and the `radio_button` branch, apply `field.hideLabel ? 'sr-only' : 'text-body font-medium text-text'` to the group heading `<p>` (design.md Decision 5).
- [x] 3.3 For the `dropdown_select` (`SelectField`), `textarea` (`TextareaField`), and every `TEXT_LIKE_INPUT_TYPES` branch (`TextField`), pass `labelClassName={field.hideLabel ? 'sr-only' : undefined}`.
- [x] 3.4 For the `file_upload` (`FileUploadField`) branch, pass `labelClassName={field.hideLabel ? 'sr-only' : undefined}`.
- [x] 3.5 Confirm `static_text` needs no change — it doesn't render `field.label` at all (already fixed in a prior change this session).

## 4. Admin Field Properties panel

- [x] 4.1 In `FieldPropertiesPanel.tsx`, add `hideLabel` local state (`useState(field.hideLabel)`), reset it alongside `isRequired`/`isActive`/`width` wherever those are reset (the effect(s) keyed on `field.id`, per the file's existing comment about the 15s background poll).
- [x] 4.2 Add a "Hide Label" `ToggleSwitch` in the same gated block as the existing "Required Field" toggle (`!isContentOnly`), mirroring its exact pattern.
- [x] 4.3 Include `hideLabel` in `save()`'s payload to `onSave`. (Forced `false` when `isContentOnly`, mirroring `isRequired`'s existing pattern — a no-op per design.md Non-Goals since `static_text` has no visible label to hide.)

## 5. Verification

- [x] 5.1 Run `tsc --noEmit` and `oxlint` clean across all changed files. Ran full-repo (not just changed files) — both clean.
- [x] 5.2 Manually verify (credentials permitting — see this session's known limitation on admin-panel click-through): toggling "Hide Label" on in the Field Properties panel and saving persists across a reload; a field with it on shows no visible label text in the visitor-facing wizard for each affected field type. **Not interactively verified** — same admin-login blocker as the prior two changes this session (no credentials for the dev backend, and no field on the live config has `hideLabel: true` yet since the toggle didn't exist until now). Regression-checked instead: re-ran the headless smoke test against the visitor wizard (`/visitor/request`) after all changes — loads with zero console/network errors, and existing fields' labels (e.g. "Registration type*") still render visibly, confirming `hideLabel`'s server-side default of `false` leaves current behavior unchanged.
- [x] 5.3 Manually verify, via the browser's accessibility tree inspector (or a screen reader) rather than only visually: a label-hidden field's label is still exposed as its accessible name. **Not interactively verified** (same blocker). Source-level: every affected branch keeps the label text inside the same `<label>`/wrapping-`<label>` element (`sr-only` only hides visually, never removes from the DOM or breaks the `htmlFor`/wrapping association) — the same idiom already proven correct at `admin-workflow-form.tsx:87`, unchanged by this task.
- [x] 5.4 Manually verify a required, label-hidden field still blocks submission when left empty, with the same validation error as a visible-label field. **Not interactively verified** (same blocker). Source-level: `hideLabel` was added purely to schema/rendering; nothing in `use-visitor-request-wizard.ts`'s required-field validation reads `hideLabel` or was touched by this change, so validation is provably unaffected.
