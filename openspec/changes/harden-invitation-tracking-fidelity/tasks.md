## 1. Re-Audit API-09 and API-10 (no code change)

- [ ] 1.1 Compared both user-supplied JSON payloads (one `group`, one
      `individual`) field-by-field against `SelfRegistrationSubmit` and its
      nested schemas — confirmed every field name (camelCase wire form),
      nesting shape, and enum value already matches, including
      `carriedItems.items` category codes and `vehicles[].vehicleType`
      codes.
- [ ] 1.2 Confirmed the multipart shape
      (`primary_contact_id_proof_file` + `visitor_id_proof_files`, matched
      to `payload.visitors` by order) matches the user's
      `<multipart part: ...>` annotations exactly.
- [ ] 1.3 Traced every field through `service.py::submit_self_registration`
      against both payloads — confirmed correct persistence, including
      real magic-byte file validation (`core/storage.py::validate_upload`),
      idempotency, and registration-type/visitor-count consistency checks.
- [ ] 1.4 Found the existing success tests assert only structural counts
      (visitor/vehicle count, `carriedItems`), not full field fidelity for
      `visitDetails`/`carriedItemsDescription`/per-vehicle/per-visitor
      detail.
- [ ] 1.5 Found `InvitationTrackingOut` (`GET /invitations/track?trackingId=`)
      omits `expectedDuration`, `departmentToVisit`, `additionalNotes`, and
      `carriedItems`/`carriedItemsDescription` — all captured during
      self-registration but never returned, despite the endpoint's own
      docstring and `docs/features/invitations.md` calling it "full
      detail."

## 2. Fix the Tracking Response Gap (design.md Decision 1)

- [ ] 2.1 `invitations/schemas.py`: add `expected_duration`,
      `department_to_visit`, `additional_notes`, `carried_items: list[str]`,
      and `carried_items_description` to `InvitationTrackingOut`.
- [ ] 2.2 `invitations/router.py::_to_tracking_out`: populate the five new
      fields from the `Invitation` row.

## 3. Close the Field-Fidelity Verification Gap (design.md Decision 2)

- [ ] 3.1 `invitations/tests.py`: add `additionalNotes` to both
      `_individual_submission()` and `_group_submission()`'s `visitDetails`,
      and add `makeModel`/`color` to the group fixture's second vehicle —
      matching both of the user's supplied JSON payloads exactly.
- [ ] 3.2 Extend `test_self_register_individual_success` to assert
      `invitation.purpose_of_visit`, `host_name_or_email`,
      `preferred_visit_date`, `preferred_visit_time`, `expected_duration`,
      `department_to_visit` all match the submitted payload.
- [ ] 3.3 Extend `test_self_register_group_success_with_visitors_and_vehicles`
      to assert `invitation.additional_notes`,
      `invitation.carried_items_description`, both visitors' `id_proof_type`
      and reachable contact, and both vehicles' full field set
      (`license_plate`, `make_model`, `color`).
- [ ] 3.4 Extend `test_track_by_tracking_id_success` to assert the five
      newly-added `InvitationTrackingOut` fields are present and correct in
      the response body.

## 4. Final Verification

- [ ] 4.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/invitations/`.
- [ ] 4.2 `ddev exec uv run mypy src/vmss_api/invitations` — clean.
- [ ] 4.3 `ddev exec uv run pytest src/vmss_api/invitations/tests.py` — all
      26 existing cases still green with the deeper assertions.
- [ ] 4.4 Full `ddev exec uv run pytest` — no regressions elsewhere.
