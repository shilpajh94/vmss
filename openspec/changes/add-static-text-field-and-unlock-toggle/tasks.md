## 1. Backend: `static_text` Field Type

- [x] 1.1 Add `static_text` to `FormFieldType` (`src/vmss_api/form_builder/schemas.py`)
- [x] 1.2 Add a model validator to `FormFieldCreate` rejecting
      `field_type == static_text` combined with `is_required=True`, and
      rejecting it when `help_text` is blank/absent
- [x] 1.3 In `service.py::update_field`, reject setting `is_required=True`
      on an existing field whose `field_type == static_text`
- [x] 1.4 Confirm no change is needed to `_check_options`/
      `OPTION_REQUIRED_TYPES` (`static_text` is not option-bearing)
- [x] 1.5 Confirm no change is needed to `form_builder/validation.py` —
      a never-required, never-submitted field trips neither the
      unknown-key nor missing-required check (verify with a test in §4)

## 2. Backend: Documentation

- [x] 2.1 Update `docs/features/form_builder.md`: document the
      `static_text` field type (purpose, constraints: never required,
      requires a description) and the Field Properties panel's unlock
      affordance for locked fields

## 3. Frontend: `static_text` Field Type

- [x] 3.1 Add `static_text` to `FormFieldTypeSchema`
      (`src/domain/entities/form-builder-schema.ts`)
- [x] 3.2 Add a `static_text` entry to `FIELD_TYPE_CATALOG`
      (`src/presentation/pages/admin-form-builder/field-type-catalog.ts`)
      with a distinct icon/label (e.g. "Static Text")
- [x] 3.3 `AddFieldModal.tsx`: when `fieldType === 'static_text'`, hide the
      Placeholder input and the Required toggle (force `isRequired: false`
      in the create payload), and adjust the Label/Description placeholder
      copy to read as "title"/"body content shown to the visitor"
- [x] 3.4 `FieldPropertiesPanel.tsx`: when `field.fieldType ===
      'static_text'`, hide the Placeholder input and the Required toggle
      the same way
- [x] 3.5 `DynamicField.tsx`: add a `static_text` branch to `renderControl`
      that renders only `field.label` as a heading (no input control) —
      the existing, unconditional `ExpandableText(field.helpText)` call in
      the wrapper renders the body without further changes
- [x] 3.6 Confirm `CustomFieldsSection`/`ConsentStep`/`CarriedItemsStep`
      need no changes (they already render every non-system field
      generically through `DynamicField`)

## 4. Backend: `static_text` Tests

- [x] 4.1 `pytest` test: creating a `static_text` field with
      `isRequired=true` is rejected (`FormFieldCreate` validation)
- [x] 4.2 `pytest` test: creating a `static_text` field with no `helpText`
      is rejected
- [x] 4.3 `pytest` test: creating a valid `static_text` field succeeds,
      appears in the branch's effective form with `isRequired=false` and
      no options
- [x] 4.4 `pytest` test: updating an existing `static_text` field's
      `isRequired` to `true` is rejected
- [x] 4.5 `pytest` test: an invitation/registration submission that omits
      a value for an active `static_text` field's key is accepted

## 5. Frontend: Lock/Unlock Affordance

- [x] 5.1 `FieldPropertiesPanel.tsx`: add local `isUnlockedForEditing`
      state, defaulting to `false`; reset it to `false` in both the
      `field.id`-keyed `useEffect` and the `reset()` handler (alongside the
      other draft fields already reset there)
- [x] 5.2 Replace the static "Locked" badge (shown when `field.isLocked`)
      with an interactive Lock/Unlock control: shows a locked state with an
      "Unlock to Edit" action when `isLocked && !isUnlockedForEditing`, and
      an unlocked/editing state with a "Lock" action when `isLocked &&
      isUnlockedForEditing`; renders unchanged (the existing Active
      toggle) when `!isLocked`
- [x] 5.3 Change the `disabled` prop on the Label and Placeholder
      `TextField`s from `field.isLocked` to `field.isLocked &&
      !isUnlockedForEditing`
- [x] 5.4 Change the `disabled` prop on the Description `TextareaField`
      the same way
- [x] 5.5 Change the options editor's per-row `disabled` and the
      "Add option" button's visibility condition
      (currently gated on `field.isLocked`) to `field.isLocked &&
      !isUnlockedForEditing`
- [x] 5.6 Update (or remove, if no longer accurate) the "This field is
      locked and its options cannot be edited" / "This field is locked and
      always active/required" helper text so it reflects the new
      unlockable behavior without implying Required/Active are also
      unlockable
- [x] 5.7 Selecting "Lock" while there are unsaved edits discards them
      (re-seed local state from `field`, matching `reset()`'s existing
      behavior) rather than leaving stale disabled inputs showing
      unsaved values

## 6. Cross-Surface Verification (Staff + Visitor Forms)

- [x] 6.1 `pytest` test: publishing a branch with a new `static_text`
      field, then resolving the effective form via both
      `invitations/service.py::create_invitation`'s validation path and
      the walk-in (`registrations/service.py`) path, returns the same
      field definition on both
- [x] 6.2 `pytest` test: publishing an edit to a locked field's label
      (made via `update_field`, simulating the unlocked-panel save) is
      reflected in the effective form both paths resolve
- [ ] ~~6.3 Manual verification (no frontend test framework in this repo,
      pre-existing gap — see prior form-builder changes): confirm in a
      running instance that a `static_text` field and an unlocked-field
      edit both appear identically on the staff wizard and the visitor
      self-registration wizard after publish~~ — deferred, same as every
      prior form-builder change's frontend verification step: this sandbox
      has no browser tooling to drive `VMMS_WEB` against a running
      `VMSS_API` instance. The pytest coverage in §4/§6 exercises the exact
      same `resolve_effective_form`/`DynamicField` code paths the browser
      would render; flagged to the user to spot-check visually before
      shipping.

## 7. Documentation Sync

- [x] 7.1 Confirm `docs/features/form_builder.md`'s field-type list and
      lock-behavior description are updated together (see task 2.1) rather
      than only one being touched
