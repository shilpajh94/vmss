## 1. Data model and config

- [x] 1.1 Add nullable, uniquely indexed `checkin_code` (String(8)) to `Invitation` and a new `alembic_tenant` migration (chain from the current head)
- [x] 1.2 Add `SmsTemplate.registration_confirmed_code` and `fast2sms_template_registration_confirmed_code`, lockout/limit settings in `core/config.py`, and update `.env.example`

## 2. Issuance

- [x] 2.1 Add `_generate_unique_checkin_code` and `get_by_checkin_code` (repository) and a get-or-create issuance step run at approval only for `sms` contacts
- [x] 2.2 Update the `sms` branch of `_send_approval_notification` to send `[tracking_id, code]` through the new template, without logging the code

## 3. Check-in and check-out by code

- [x] 3.1 Extract shared post-lookup check-in/out helpers from the QR service functions and make the QR path use them
- [x] 3.2 Add request schema (`code` constrained to 8 digits) and service functions resolving the invitation by code with a generic invalid-code 400
- [x] 3.3 Add `PATCH /code/check-in` and `/code/check-out` to `router_v2` with `response_model=Envelope[InvitationQrCheckInOut]`, `Idempotency-Key`, host notification and audit log
- [x] 3.4 Add `slowapi` limit and Redis failure-counter lockout (fail closed), WARNING log without the code

## 4. Tests

- [x] 4.1 Issuance: SMS contact gets a code, email/WhatsApp do not, redelivery keeps the same code, uniqueness retry
- [x] 4.2 SMS dispatch uses the new template with tracking ID and code; not-configured is not retried
- [x] 4.3 Check-in by code: happy path, idempotent repeat, 410 expired, 425 too early, 409 flagged, invalid and malformed code
- [x] 4.4 Check-out by code: happy path, 409 when not checked in, re-entry after check-out
- [x] 4.5 Rate limit and lockout (429 even for a valid code after failures); QR endpoints still work for an SMS invitation
- [x] 4.6 Tenant-isolation test: a code from another tenant's schema is not found

## 5. Docs and verification

- [x] 5.1 Update `docs/features/invitations.md` (endpoints, settings, DLT template text to register) and `docs/features/background-jobs.md` if the approval task changes
- [ ] 5.2 Run `ruff check`, `ruff format --check`, `mypy` on touched modules and the full `pytest` suite; confirm `tests/test_api_documentation.py` passes
