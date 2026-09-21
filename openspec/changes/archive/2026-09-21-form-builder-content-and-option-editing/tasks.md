## 1. Shared Expandable-Text Component

- [x] 1.1 Add a reusable expandable-text component (e.g.
      `src/presentation/components/ui/ExpandableText.tsx` in `VMMS_WEB`)
      that takes a plain-text string, renders its first sentence by
      default, and shows a "See more"/"See less" toggle when the text has
      more than one sentence
- [x] 1.2 Implement the first-sentence split (on the first `.`/`!`/`?`
      followed by whitespace or end-of-string) and the case where no
      sentence boundary is found — render the full text with no toggle
- [ ] ~~1.3 Cover the component with unit tests: multi-sentence text
      (truncated + expand + collapse), single-sentence text (no toggle),
      empty/`null` text (renders nothing)~~ — see "5. Tests" below

## 2. Admin: Field Creation (`AddFieldModal.tsx`)

- [x] 2.1 Add a "Description" textarea to the "Configure Properties"
      section, available for every field type (not gated by
      `OPTION_REQUIRED_FIELD_TYPES` or any other type check)
- [x] 2.2 Include the entered value as `helpText` in the
      `FormFieldCreateInput` payload passed to `onCreate`, trimmed, and
      omitted (`undefined`) when left blank
- [x] 2.3 Reset the description field along with the rest of the form's
      local state after a successful create (`reset()`)

## 3. Admin: Field Editing (`FieldPropertiesPanel.tsx`)

- [x] 3.1 Add a "Description" textarea, seeded from `field.helpText`,
      disabled when `field.isLocked` (matching the existing
      label/placeholder pattern), and included as `helpText` in the
      `FormFieldUpdateInput` passed to `onSave`
- [x] 3.2 Add an options editor — one text input per existing option with
      a remove button, plus an "Add option" affordance — shown only for
      `checkbox_list`, `dropdown_select`, and `toggle_switch` fields that
      currently have a non-empty `options` list or are of an
      option-required type; disabled when `field.isLocked`
- [x] 3.3 Support reordering option rows (reuse the drag-handle pattern
      `SortableFieldRow` already uses for field ordering)
- [x] 3.4 Include the edited `options: string[]` in the
      `FormFieldUpdateInput` passed to `onSave`
- [x] 3.5 Surface the backend's "must declare a non-empty options list"
      rejection (when every option is removed from an option-required
      field type) as an inline error, and leave the panel's local state
      showing the last-saved options rather than the emptied draft
- [x] 3.6 Reset both the description and options editor state in the
      panel's `reset()` handler and in the `useEffect` that re-seeds local
      state when `field` changes

## 4. Visitor-Facing Rendering (`DynamicField.tsx`)

- [x] 4.1 Render `field.helpText` via the new expandable-text component
      beneath each field type's existing input/control, for every branch
      of `DynamicField` (including the "not supported inline yet"
      fallback branch) — factor this into one shared render path rather
      than repeating it per branch
- [x] 4.2 Confirm no description area renders when `field.helpText` is
      `null` (no empty wrapper, no layout shift)

## 5. Tests

**Skipped deliberately** — VMMS_WEB has no test framework at all (no vitest/jest,
no `test` script, zero `.test.*` files anywhere in `src/`), the same pre-existing
gap already documented in `fix-wizard-inactive-steps`'s tasks.md. Writing these
tests would mean standing up a test runner and React Testing Library from
scratch first, which isn't scoped in this change's design/tasks and is a
separate piece of work. Flagged to the user during this apply session
(2026-09-21); revisit if/when this repo gets a test framework.

- [ ] ~~5.1 `AddFieldModal` test: creating a field with a description
      includes `helpText` in the create payload; leaving it blank omits it~~
- [ ] ~~5.2 `FieldPropertiesPanel` tests: editing description on an unlocked
      field updates the save payload; description input is disabled for a
      locked field; adding/removing/reordering options on an unlocked
      option-bearing field updates the save payload; options editor is
      disabled for a locked field; emptying all options and saving
      surfaces the rejection and does not clear the panel's displayed
      options~~
- [ ] ~~5.3 `DynamicField` tests: a field with a multi-sentence description
      renders truncated with a working expand/collapse toggle; a field
      with no description renders no description area; behavior is
      consistent across at least one field type from each existing render
      branch (plain toggle, checkbox list/optioned toggle, dropdown,
      textarea, text-like, fallback)~~

## 6. Documentation

- [x] 6.1 Update `docs/features/form_builder.md` to document that a
      field's description (`helpText`) and an existing option-bearing
      field's options are now editable from the admin UI after creation,
      not just at creation time
