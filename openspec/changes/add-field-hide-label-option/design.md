## Context

See proposal.md - Why. Current code (confirmed by reading the source):

- `FormFieldOutSchema`/`FormField` (`src/domain/entities/form-builder-schema.ts`) has no `hideLabel` property today; neither do `FormFieldCreateInput`/`FormFieldUpdateInput`.
- `FieldPropertiesPanel.tsx` already has an established pattern for a boolean field property: `isRequired` — local `useState`, a `ToggleSwitch` in the "Validation Rules" section, included in `save()`'s payload to `onSave` (`FormFieldUpdateInput`). `width` follows a parallel but different pattern — `useState`, a two-button selector, included in `save()`'s payload — but is **not** exposed in `AddFieldModal.tsx` at field creation; it's edit-only, defaulting server-side for a new field.
- `AddFieldModal.tsx`'s create payload (`FormFieldCreateInput`) is a fixed, explicit object literal (`key`, `label`, `placeholder`, `helpText`, `fieldType`, `isRequired`, `options`) — it does not spread `width` or any other edit-only property.
- Three of the five UI primitives `DynamicField.tsx` renders already accept a `labelClassName?: string` override with no other change needed: `TextField`, `SelectField`, `TextareaField` (`src/presentation/components/ui/*.tsx`). This is a real, already-used codebase idiom for visually hiding a label while keeping it accessible: `admin-workflow-form.tsx:87` already does `labelClassName="sr-only"` on a `SelectField`. Tailwind's built-in `sr-only` utility (already relied on elsewhere, e.g. `ToggleSwitch.tsx:22`) visually hides an element while keeping it in the accessibility tree — the label stays linked to its input via `htmlFor`/`id`, so it remains that input's accessible name exactly as if it were visible.
- `FileUploadField` hardcodes its label's class (`"text-body font-medium text-text"`) with no override prop — needs one added, mirroring the other three.
- `Checkbox` (used for `checkbox_single` and an option-free `toggle_switch`) has a different shape: a single `<label>` wraps both the `<input type="checkbox">` and a `<span>{children}</span>` holding the visible label text (implicit label association via wrapping, not `htmlFor`). No `labelClassName`-style prop exists.
- `checkbox_list` and `radio_button` (in `DynamicField.tsx`'s `renderControl`) each render their own bespoke group heading — `<p className="text-body font-medium text-text">{field.label}</p>` — above a list of `Checkbox`/radio inputs. This heading is the only accessible identification of the *group* as a whole (each option's own visible text is the option's own label, not the field's).
- `static_text` no longer renders `field.label` as a visible heading at all (a prior change in this session moved it to render only `helpText`) — `hideLabel` has nothing to act on there.

## Goals / Non-Goals

**Goals:**
- Let an admin hide a field's visible label from visitors while the label remains that field's accessible name for assistive technology — matching the backend's stated intent exactly.
- Reuse the codebase's existing `sr-only`/`labelClassName` idiom rather than introducing a new accessibility pattern (e.g. `aria-label`-only, which would be a second, inconsistent way of doing the same thing).

**Non-Goals:**
- No change to `AddFieldModal.tsx`/field creation — `hideLabel` is edit-only, following `width`'s existing precedent, not because the backend disallows it at creation (the task notes it's optional there) but because this codebase already has an established convention for exactly this category of property (set once created, defaults server-side) and matching it is simpler than introducing two different conventions for two structurally similar properties.
- No change to `static_text` rendering — it already shows no visible label, so `hideLabel` is a no-op for it; the Field Properties panel's "Hide Label" toggle SHALL follow `isContentOnly`'s existing gating (hidden/not applicable for `static_text`, same as the "Validation Rules" section already is) rather than offering a control with no visible effect.
- No change to validation logic anywhere — confirmed by the backend reference and unaffected by anything in this design, since `hideLabel` never reaches any required-value check.
- No visible "required" asterisk preserved when a label is hidden — the `*` is currently rendered inside the same `<label>` element as the text (`TextField`/`SelectField`/`FileUploadField`), so hiding the label hides the asterisk too. Not solved here (e.g. with a separate always-visible asterisk) since nothing in the proposal asks for it and it adds a second rendering path per primitive for a cosmetic detail.

## Decisions

**1. Implementation is `sr-only` + kept-linked `<label>`, not `aria-label`.**
The backend's framing ("keep label as the input's aria-label (or equivalent)") explicitly allows an equivalent. This codebase already has one, in production use (`admin-workflow-form.tsx:87`). A linked `<label htmlFor>`/wrapping `<label>` is the more robust, more broadly-supported accessible-naming mechanism (also preserves the label as part of the input's click target, which `aria-label` alone would not, though that only matters for `Checkbox`'s wrapping-`<label>` shape here). Using it also means zero new accessibility pattern to reason about — the existing idiom already does exactly what's needed.
Alternative considered: add `aria-label={field.hideLabel ? field.label : undefined}` to each primitive's underlying `<input>`/`<select>` and stop rendering the `<label>` element when `hideLabel`. Rejected: more code (a second labeling path per primitive, decided per-render), inconsistent with the one already-proven `sr-only` idiom in this codebase, and loses the click-target benefit for `Checkbox`.

**2. `TextField`/`SelectField`/`TextareaField` need no prop changes — `DynamicField.tsx` just passes `labelClassName={field.hideLabel ? 'sr-only' : undefined}`.**
They already accept `labelClassName`. This is the smallest possible change for 3 of the 5 control types `DynamicField.tsx` renders (`dropdown_select`, `textarea`, and every `TEXT_LIKE_INPUT_TYPES` entry: `text`/`email`/`phone`/`number`/`date_picker`/`time_picker`).

**3. `FileUploadField` gets a `labelClassName?: string` prop added, mirroring the other three exactly.**
Same prop name/shape/default (`undefined` → today's existing visible class) as `TextField`/`SelectField`/`TextareaField`, for consistency — not a new pattern, just extending this one component to match its siblings.

**4. `Checkbox` gets a `hideLabel?: boolean` prop (not `labelClassName`, since it has no single label-holding element with a variable class today) that wraps its `<span>{children}</span>` in `sr-only` when true.**
The `<input>` stays inside the same `<label>` element either way, so the accessible-name association is unaffected by hiding the `<span>`'s visual rendering — only the visible text disappears. Named `hideLabel` (matching the domain field's own name) rather than `labelClassName`, since `Checkbox` has no separate element whose class would need overriding — the whole `<span>` either shows or is visually hidden, a boolean, not an arbitrary class string.

**5. `checkbox_list`/`radio_button`'s own group heading (`<p>{field.label}</p>`) gets the same `sr-only`-when-`hideLabel` treatment as `TextField`, applied directly in `DynamicField.tsx` (className computed inline, same as decision 2) rather than through a shared prop, since this `<p>` isn't inside a reusable primitive.**
This keeps the group's label present in the accessibility tree (a screen reader reading through the page still encounters the text, just not visually) — not a perfect `role="group" aria-label`/`<fieldset><legend>` structure (which nothing else in this codebase uses today), but consistent with every other `sr-only` use here and sufficient for the stated requirement without introducing a new ARIA pattern this codebase doesn't otherwise have. Flagged as a known limitation below, not silently assumed equivalent to a true group label.

## Risks / Trade-offs

- **[`sr-only` group heading isn't a true `aria-labelledby`/`<fieldset><legend>` group label]** → For `checkbox_list`/`radio_button` specifically, a visually-hidden `<p>` sibling is a weaker accessibility guarantee than a proper group-labeling construct (some screen readers announce a `<fieldset><legend>` when entering the group; a preceding `sr-only` paragraph is read as regular content, not as an explicit group label). Accepted here because: (a) no `<fieldset>/<legend>` pattern exists anywhere else in this codebase to extend, (b) the requirement's own scenario language ("the field's label is announced ... the same as it would be if the label were visible") is satisfied — the *visible* version today is also just a plain `<p>`, not a `<legend>`, so this preserves parity rather than regressing it. A follow-up to adopt `<fieldset>/<legend>` for grouped fields generally would be a separate, larger change.
- **[Required-field asterisk disappears with the label]** → Accepted per Non-Goals; purely cosmetic, not a validation change.

## Migration Plan

No data migration — `hideLabel` defaults to `false` server-side, so every existing field renders exactly as before until an admin opts in. Standard frontend release; no rollback complexity.
