## 1. Frontend: Hide Required Control for Content-Only Fields

- [x] 1.1 `SortableFieldRow.tsx`: don't render the Required
      checkbox/label when the field's type is in
      `CONTENT_ONLY_FIELD_TYPES` (`field-type-catalog.ts`)
- [x] 1.2 Confirm `onToggleRequired` is simply not wired up for that row
      (no dead handler left reachable) and every other field type's row is
      unaffected

## 2. Backend: Field-Type Change on Update

- [x] 2.1 Add `field_type: FormFieldType | None = None` to `FormFieldUpdate`
      (`src/vmss_api/form_builder/schemas.py`)
- [x] 2.2 In `service.py::update_field`, reject a `field_type` change when
      `field_row.is_system` is `true`
- [x] 2.3 Compute the field's resulting type/required/help_text/options
      after applying the update (payload value where provided, existing
      row value otherwise) and re-run the same checks
      `FormFieldCreate` applies at creation:
      - resulting type in `OPTION_REQUIRED_TYPES` with no non-empty
        resulting `options` → reject
      - resulting type `static_text` with resulting `is_required=True`, or
        blank resulting `help_text` → reject
- [x] 2.4 When the resulting type is not option-bearing and the update
      doesn't itself set `options`, clear the field's stored `options` to
      `null`
- [x] 2.5 Confirm changing a field's type away from `static_text` needs no
      extra handling (no constraint applies to the new type unless it is
      itself `static_text` or option-required, both covered by 2.3)
- [x] 2.6 **(discovered during implementation, not in the original scope)**
      Fix `update_field`'s locked-field `isActive`/`isRequired` guard and
      the new `field_type`-changed guard to compare an *actual attempted
      transition* (new value differs from the field's current value), not
      merely whether the key is present in the payload — the admin UI's
      save payload always resends every property it manages at its current
      value when untouched (matching every other field), so a presence-only
      check would reject any save on a locked field whose `isRequired` is
      already `false` (e.g. Email, Phone, Host), and — once `fieldType` is
      always resent too — every single save on any system field
      (`test_locked_field_with_false_required_state_can_still_be_saved`,
      `test_toggleable_system_field_can_be_saved_with_unchanged_field_type_resent`)

## 3. Frontend: Editable Field Type in Field Properties Panel

- [x] 3.1 `FieldPropertiesPanel.tsx`: add local `fieldType` draft state,
      seeded from `field.fieldType`, reset alongside the panel's other
      draft fields (the `field.id`-keyed `useEffect` and `reset()`)
- [x] 3.2 Recompute `showOptionsEditor`/`isContentOnly` from the draft
      `fieldType` state instead of `field.fieldType`, so the panel's
      Options editor and Placeholder/Required visibility update live as
      the admin changes the selection
- [x] 3.3 Make the "Field Type" `SelectField` editable (options from
      `FIELD_TYPE_CATALOG`, matching `AddFieldModal`'s catalog) when
      `!field.isSystem`; keep it disabled, showing only the current type,
      when `field.isSystem`
- [x] 3.4 Include the draft `fieldType` in the `FormFieldUpdateInput` sent
      by `save()`
- [x] 3.5 Add `fieldType?: FormFieldType` to `FormFieldUpdateInput`
      (`src/domain/entities/form-builder-schema.ts`)
- [x] 3.6 Surface the backend's type-change rejections (option-required
      type with no options; `static_text` still required or with no
      description) as the existing inline `saveError`, consistent with how
      other validation errors already surface in this panel

## 4. Frontend: Simplify Lock/Unlock Button Copy

- [x] 4.1 `FieldPropertiesPanel.tsx`: change the Lock/Unlock button's
      visible text from `'Locked — Unlock to Edit'`/`'Editing — Lock'` to
      `'Unlock to Edit'`/`'Lock'` (icon continues to convey which state is
      current)

## 5. Backend Tests

- [x] 5.1 `pytest` test: changing a system field's type is rejected (422)
- [x] 5.2 `pytest` test: changing an admin-authored field's type succeeds
      and is reflected in a subsequent read
- [x] 5.3 `pytest` test: changing a field's type to `dropdown_select`/
      `checkbox_list` without supplying options (and none already saved)
      is rejected
- [x] 5.4 `pytest` test: changing a field's type to `dropdown_select` while
      supplying `options` in the same request succeeds
- [x] 5.5 `pytest` test: changing an existing `checkbox_list` field's type
      to `text` clears its stored `options`
- [x] 5.6 `pytest` test: changing a field's type to `static_text` while it
      is still `isRequired=true` is rejected; while it has no `helpText` is
      rejected
- [x] 5.7 `pytest` test: changing an existing `static_text` field's type to
      `text` succeeds and the field can subsequently be marked required
- [x] 5.8 `pytest` test: publishing a type change is reflected in
      `GET /form-builder/effective`

## 6. Documentation

- [x] 6.1 Update `docs/features/form_builder.md` to note that an
      admin-authored field's type is now editable after creation (system
      fields excepted), and correct the Lock/Unlock button copy reference
      if the doc quotes the old two-part label

## 7. Manual Verification

- [ ] ~~7.1 Manual verification (no frontend test framework in this repo,
      pre-existing gap): confirm in a running instance that (a) a
      `static_text` field's row shows no Required checkbox, (b) an
      admin-authored field's type can be changed and the panel's other
      controls update live, (c) a system field's type control stays
      disabled, and (d) the Lock/Unlock button reads "Unlock to Edit"/
      "Lock" with no state prefix~~ — deferred, same as every prior
      form-builder change: this sandbox has no browser tooling to drive
      `VMMS_WEB` against a running `VMSS_API` instance. `tsc -b` and
      `oxlint` both pass clean on every touched file, and the pytest suite
      (including two regression tests for a save-payload bug found while
      implementing this) covers the underlying `update_field` behavior the
      browser would exercise. Flagged to the user to spot-check visually
      before shipping.
