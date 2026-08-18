## 1. Router (`invitations/router.py`)

- [x] 1.1 Built `_required_fields_summary()` from `InvitationCreate`,
      `InvitationPrimaryContactCreate`, `VisitorSubmit`, `VisitDetailsSubmit`,
      `CarriedItemsSubmit`, `VehicleSubmit`, and `ConsentsSubmit`'s own
      `.model_json_schema()["required"]` lists (design.md Decision 2 —
      generated, not hand-typed).
- [x] 1.2 Appended that summary to `_PAYLOAD_DESCRIPTION`, after the existing
      example JSON blocks. Verified rendered output directly against
      `app.openapi()`.

## 2. Validation-completeness tests (`invitations/tests.py`)

- [x] 2.1 Added `test_create_invitation_missing_required_top_level_field_rejected`
      (parametrized over `registrationType`/`primaryContact`/`visitDetails`/
      `consents`) — all 422, confirming validation was already correct.
- [x] 2.2 Added invalid-enum tests: `idProofType`, `vehicleType`, and a
      carried-item category — all 422.
- [x] 2.3 Added `test_create_invitation_vehicle_missing_license_plate_rejected`
      and `test_create_group_invitation_visitor_missing_full_name_rejected`
      — both 422.
- [x] 2.4 Added `test_invitation_payload_description_matches_schema_requirements`
      — independently recomputes each schema's `required` list (does not
      call `_required_fields_summary()`) and asserts every field appears in
      the description text.

## 3. Real dispatch verification (`invitations/tests.py`)

- [x] 3.1 Added `_MAILPIT_BASE_URL`/`_MAILPIT_API_URL` module constants.
- [x] 3.2 Added `test_send_visit_confirmation_delivers_email_with_qr_via_mailpit`:
      real `SmtpEmailSender` (not monkeypatched), real SMTP send, queries
      Mailpit's HTTP API for a message matching a unique `tracking_id` +
      recipient, asserts subject and single attachment.
- [x] 3.3 Asserted attachment `ContentType: image/png` and that Pillow opens
      and `.verify()`s the fetched bytes as a valid PNG.
- [x] 3.4 Matches by unique `tracking_id` (embedded in the email body/
      Snippet) + unique generated recipient address, not "latest message" —
      safe against a shared, non-empty Mailpit inbox across runs.

## 4. Docs

- [x] 4.1 `docs/features/invitations.md`: added a note that no Celery worker
      runs by default in this DDEV environment, the command to start one
      manually, and where to find Mailpit's UI for manual verification.

## 5. Final Verification

- [x] 5.1 `ddev exec uv run ruff check .` and `ddev exec uv run ruff format --check .`
      — both clean across the whole repo.
- [x] 5.2 `ddev exec uv run mypy src/vmss_api/invitations` — clean, 11
      source files (required adding explicit `list[type[BaseModel]]`
      annotations in two places where mypy couldn't infer a common type
      across a list of different Pydantic model classes).
- [x] 5.3 `ddev exec uv run pytest` — full suite green, 186/186 passed
      (up from 175 before this change's 11 new tests), no regressions.
- [x] 5.4 Manually inspected Mailpit's API response after running the new
      test — confirmed a legible "Your visit is confirmed" email with the
      correct tracking ID in the body and a genuine `visit-qr.png`
      attachment, addressed to the test's generated recipient. Left in the
      inbox (not auto-deleted) specifically so this could be checked and so
      a human can look at it directly in Mailpit's web UI too.
