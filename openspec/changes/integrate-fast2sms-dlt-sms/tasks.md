## 1. Configuration

- [x] 1.1 Add `fast2sms_api_key`, `fast2sms_sender_id`, `fast2sms_base_url`, and six `fast2sms_template_*` settings to `core/config.py`; remove `twilio_*` and `sms_gateway_*`
- [x] 1.2 Update `.env.example`: add all `FAST2SMS_*` keys (secrets blank), remove Twilio and `SMS_GATEWAY_*` entries and fix their comments

- [x] 1.3 Add `fast2sms_whatsapp_phone_number_id`, `fast2sms_whatsapp_api_version`, `fast2sms_whatsapp_language_code` and six `fast2sms_whatsapp_template_*` settings to `core/config.py` and `.env.example`; drop the unused `whatsapp_gateway_*` placeholders

## 2. Shared Fast2SMS client

- [x] 2.1 Create `core/sms.py` with `SmsTemplate`, error classes, phone normalisation, variable sanitising (strip `|`/newlines, 30-char cap)
- [x] 2.2 Implement `Fast2SmsSender.send` with `httpx.AsyncClient` (GET bulkV2, `route=dlt`, `Authorization` header, timeout), success = 200 and `return: true`
- [x] 2.3 Per-call not-configured check (key, sender ID, template ID) and masked `WARNING` logging on failure, with no key/code/full number logged

- [x] 2.4 Create `core/whatsapp.py` with `WhatsAppTemplate` and `Fast2WhatsAppSender.send` (`httpx.AsyncClient`, POST `/dev/whatsapp/{version}/{phone_number_id}/messages`, template + body variables, `91`+10-digit number, success = 200 and `messages[0].id`), reusing the shared errors, normaliser and masked logging; OTP template also sends the `url` button parameter
- [x] 2.5 Per-call not-configured check (key, phone number ID, template name)

## 3. Wire OTP

- [x] 3.1 In `identity_verification/senders.py` replace `TwilioSmsSender`/`UnconfiguredSmsSender` with the shared sender, keeping `GatewayNotConfiguredError`/`SmsDispatchError` mapping to the existing 503 behaviour and non-caching rule
- [x] 3.2 In `identity_verification/service.py` send `SmsTemplate.otp` with `[code, minutes]` for the `sms` channel

- [x] 3.3 In `identity_verification/senders.py` replace `UnconfiguredWhatsAppSender` with the shared WhatsApp sender and send `WhatsAppTemplate.otp` with `[code]` for the `whatsapp` channel

## 4. Wire invitation SMS and WhatsApp

- [x] 4.1 Replace the `UnconfiguredSmsSender` in `invitations/notifications.py` with the shared sender
- [x] 4.2 Change `invitations/tasks.py::_dispatch` to take `sms_template` + `sms_variables`; update the pending, confirmed, denied, reschedule and details-changed tasks (shorten the details-changed SMS)
- [x] 4.4 Add `whatsapp` to `ContactMethod` and `_require_contact_for_method` in `invitations/schemas.py` (phone required); check `form_builder/defaults.py` and any other place that enumerates contact methods
- [x] 4.5 Add the WhatsApp sender to `invitations/notifications.py` and a `whatsapp` branch in `tasks.py::_dispatch`; pass WhatsApp template + variables from the five tasks
- [x] 4.3 Exclude not-configured and invalid-number errors from Celery autoretry; log `ERROR` with tenant and invitation id on exhaustion

## 5. Cleanup

- [x] 5.1 Remove `twilio` from `pyproject.toml` and refresh `uv.lock` with `uv`
- [x] 5.2 Update docs under `docs/features/` for identity verification and invitations to describe Fast2SMS, the six DLT templates (text from design.md), the six WhatsApp templates and the `whatsapp` contact method

## 6. Tests

- [x] 6.1 Unit tests for `core/sms.py` with a mocked `httpx` transport: request shape, `|` joining, phone normalisation, `return: false`, timeout, not-configured, invalid number
- [x] 6.2 Rewrite the Twilio tests in `identity_verification/tests.py` against the new sender (success, unconfigured 503, failure 503 without leak, failure not idempotency-cached)
- [x] 6.3 Invitation tests: each lifecycle event with an `sms`-preferring contact sends one SMS with the right template and variables and no email; `email` contact sends no SMS
- [x] 6.4 Unit tests for `core/whatsapp.py` with a mocked `httpx` transport: request shape, OTP button parameter, number normalisation, missing message id, timeout, not-configured, invalid number
- [x] 6.5 OTP over `whatsapp` tests (success, unconfigured 503, failure 503 without leak) and invitation tests: each lifecycle event with a `whatsapp`-preferring contact sends one WhatsApp message with the right template and variables and no email/SMS; `whatsapp` without phone is rejected; `email`/`sms` send no WhatsApp
- [x] 6.6 Run `ruff check`, `ruff format --check`, `mypy` on touched `core/` modules and the full `pytest` suite

## 7. Rollout check

- [ ] 7.1 With real DLT-approved templates, send an OTP and one invitation SMS to a real number and confirm delivery
- [ ] 7.2 With Meta-approved WhatsApp templates, send an OTP and one invitation WhatsApp to a real number and confirm delivery
