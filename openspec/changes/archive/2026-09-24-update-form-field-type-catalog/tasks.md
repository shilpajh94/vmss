## 1. Field Type Catalog

- [x] 1.1 In `src/vmss_api/form_builder/schemas.py`, remove the
      `dynamic_table`, `rich_text_block`, and `signature_pad` members from
      `FormFieldType`; add `checkbox_single = "checkbox_single"` and
      `radio_button = "radio_button"`.
- [x] 1.2 Add `FormFieldType.radio_button` to `OPTION_REQUIRED_TYPES`;
      update the comment above it to mention `radio_button` alongside
      `dropdown_select`/`checkbox_list`. Leave `checkbox_single` out of
      the set (see design.md Decisions).

## 2. Submission-Time Validation

- [x] 2.1 In `src/vmss_api/form_builder/validation.py::_validate_value_against_field`,
      fold `field_type == "radio_button"` into the existing
      single-value-membership branch (currently the `dropdown_select`/
      `toggle_switch` `elif`), so a `radio_button` value not in its
      declared `options` is rejected with 422 the same way an invalid
      `dropdown_select` value is.
- [x] 2.2 Confirm `checkbox_single` needs no new branch — it follows the
      same option-free path `toggle_switch` already takes when it has no
      `options` (no code change here; verify by reading the updated
      function).

## 3. Service-Layer Type-Change Re-Validation

- [x] 3.1 In `src/vmss_api/form_builder/service.py`, verify the field-update
      path's `resulting_needs_options`/options-clearing logic (around the
      `OPTION_REQUIRED_TYPES` check) picks up `radio_button` with no code
      change, since it reads from `OPTION_REQUIRED_TYPES` rather than a
      hardcoded type list — add a code comment only if the existing one
      there enumerates types by name.

## 4. Tests

- [x] 4.1 In `src/vmss_api/form_builder/tests.py`, add/extend field-creation
      tests: creating a `radio_button` field without `options` is rejected
      (422); creating one with a non-empty `options` list succeeds.
- [x] 4.2 Add a test that creating a `checkbox_single` field with no
      `options` succeeds.
- [x] 4.3 Add a test that `dynamic_table`, `rich_text_block`, and
      `signature_pad` are no longer accepted as a `fieldType` on field
      create (422).
- [x] 4.4 Add/extend a submission-validation test (wherever
      `_validate_value_against_field`/invitation or registration
      submission is covered) asserting an out-of-list `radio_button`
      value is rejected at submission, matching the existing
      `dropdown_select` invalid-value test.
- [x] 4.5 Add a field-type-change test: changing an existing unlocked
      field's type to `radio_button` without an `options` list is
      rejected, matching the existing `dropdown_select`/`checkbox_list`
      type-change coverage.
- [x] 4.6 Run `ddev exec uv run pytest src/vmss_api/form_builder/tests.py`
      and confirm the full suite passes. Also ran
      `src/vmss_api/invitations/tests.py` (consumer of
      `validation.py`/`allowed_options_for_system_field`) since this
      change touches shared form-builder validation code: 326/327 passed;
      the one failure
      (`test_get_invitation_detail_includes_id_proof_url_with_documents_view`)
      is a pre-existing flake unrelated to this change —
      `InvitationVisitorFactory` doesn't pin `id_proof_storage_key`, so
      `polyfactory` randomly generates `None` for that nullable column on
      some runs; passed cleanly in isolation.

## 5. Documentation

- [x] 5.1 Update `docs/features/form-builder.md` (or the equivalent
      feature doc, if one lists supported field types) to drop the three
      removed types and add `checkbox_single`/`radio_button`, per
      `project-rules.md`'s "New Features" documentation expectation.
- [ ] 5.2 Note the breaking removal (`dynamicTable`/`richTextBlock`/
      `signaturePad` no longer accepted) in the PR description per
      `api-conventions.md` §2, since the React portal is a separate repo
      that may still reference them in its own field-type picker.
