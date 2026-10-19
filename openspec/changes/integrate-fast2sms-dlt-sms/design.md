## Context

SMS today: `identity_verification/senders.py` has `TwilioSmsSender` (OTP only, free-text body); `invitations/notifications.py` has only `UnconfiguredSmsSender`, so `invitations/tasks.py::_dispatch` raises for any `sms`-preferring visitor. Two separate `SmsSender` protocols exist (deliberately not merged, see their docstrings). Fast2SMS DLT takes a template ID and `|`-joined variables, not a body. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One Fast2SMS DLT client used by both OTP and invitation SMS.
- Template-based send API that makes it impossible to send untemplated text.
- Replace Twilio fully.

**Non-Goals:**
- Delivery-status webhooks (`udf1-3` and WhatsApp webhooks), scheduled SMS (`schedule_time`), per-tenant DLT/WhatsApp config, WhatsApp session (free-text) messages, media/button templates other than the OTP one, a general `notifications/` package. Registering DLT templates with the operator is an ops prerequisite.

## Decisions

1. **Shared client in `core/sms.py`**, not in either feature. Both features need it; putting it in `core/` avoids one importing the other. It exposes `Fast2SmsSender.send(*, to, template: SmsTemplate, variables: Sequence[str])`, plus `SmsTemplate` (str enum: `otp`, `registration_pending`, `registration_confirmed`, `registration_denied`, `visit_rescheduled`, `visit_details_changed`) and the errors `SmsNotConfiguredError`, `SmsDispatchError`. The existing per-feature error classes become aliases/subclasses so current `except` sites and the 503 mapping keep working. Alternative (two copies, matching the "don't merge" note) rejected: that note was about email/SMS abstractions diverging, and duplicating an HTTP client plus DLT mapping buys nothing.
2. **HTTP via `httpx.AsyncClient`**, GET `https://www.fast2sms.com/dev/bulkV2`, `Authorization: <key>` header, 10 s timeout. Native async, so no `anyio.to_thread` needed (Twilio's sync SDK needed it). Success means HTTP 200 and `return: true`; anything else is `SmsDispatchError`. Fast2SMS documents no error codes, so the response `message` is logged verbatim (no secrets in it).
3. **Settings in `core/config.py`**: `fast2sms_api_key`, `fast2sms_sender_id`, `fast2sms_base_url` (default the production URL, for tests), and `fast2sms_template_<type>` per template; all optional, blank = unconfigured. Remove `twilio_*` and `sms_gateway_*`. `.env.example` updated per git-workflow §6 (secrets blank, no placeholder).
4. **Configured check is per call**, not at import: the sender reads settings when sending and raises `SmsNotConfiguredError` if the key, sender ID, or that template's ID is blank. Replaces the import-time `_twilio_configured` switch so a template added later doesn't need a restart-order trick and tests can monkeypatch settings.
5. **Variable handling**: variables are stringified, `|` replaced by space, newlines collapsed, and truncated to 30 chars (DLT variable limit) — the limit is a constant in one place. The edit-details SMS drops from five details to tracking ID + date + time, since the multi-line version cannot fit a DLT template. Proposed template texts (to register on DLT, `{#var#}` order = variable order):
   - otp: `Your verification code is {#var#}. It expires in {#var#} minutes. Do not share it.`
   - registration_pending: `Your registration is awaiting approval. Tracking ID: {#var#}.`
   - registration_confirmed: `Your registration is confirmed. Tracking ID: {#var#}. Show your QR at check-in.`
   - registration_denied: `Your registration was not approved. Tracking ID: {#var#}. Reason: {#var#}`
   - visit_rescheduled: `Your visit is rescheduled to {#var#} {#var#}. Tracking ID: {#var#}.`
   - visit_details_changed: `Details of your visit {#var#} changed. New slot {#var#} {#var#}.`
   The confirmed SMS previously said "attached QR code", which is impossible by SMS, so the new text drops it (a QR link is a follow-up, see Non-Goals).
6. **Phone normalisation** in the sender: strip spaces/dashes, drop leading `+91`/`91`/`0`, require exactly 10 digits starting 6-9, else raise a non-retryable `SmsInvalidNumberError`. Alternative (validate at API input) is a breaking tightening under api-conventions §2, so out of scope.
7. **Call sites**: `invitations/tasks.py::_dispatch` replaces `sms_body: str` with `sms_template` + `sms_variables`; the five task bodies pass those instead of building strings. `identity_verification/service.py` calls the sender with `SmsTemplate.otp` and `[code, minutes]`. Tasks keep their existing `autoretry_for`/backoff (background-jobs §3); `SmsInvalidNumberError` and `SmsNotConfiguredError` are excluded from retry so a bad number doesn't spin.
8. **Logging**: masked recipient only (existing `mask_identifier`), never the key, code or full number. Logger is the central `structlog` one.

9. **WhatsApp client in `core/whatsapp.py`**: `Fast2WhatsAppSender.send(*, to, template: WhatsAppTemplate, variables: Sequence[str])` with the same six-member template enum idea and the error types shared with `core/sms.py` (`SmsNotConfiguredError`/`SmsDispatchError`/`SmsInvalidNumberError` are defined once in `core/sms.py` and re-used, to avoid a third error hierarchy; alternative of renaming them to generic `Message*` errors is deferred as churn). Uses `httpx.AsyncClient`, `POST .../dev/whatsapp/{version}/{phone_number_id}/messages`, JSON body (`messaging_product: whatsapp`, `to`, `type: template`, `template.name`, `template.language.code`, one `body` component with `text` parameters), same `Authorization` key. Success means HTTP 200 and a non-empty `messages[0].id` (Fast2SMS documents no error body, so the response text is logged verbatim, minus secrets). Number format is `91` + 10 digits, reusing the normaliser from Decision 6. The OTP template additionally sends the code as the `url` button parameter at index 0, per Fast2SMS's authentication template docs.
10. **WhatsApp settings**: `fast2sms_whatsapp_phone_number_id`, `fast2sms_whatsapp_api_version` (default `v26.0`), `fast2sms_whatsapp_language_code` (default `en`), and `fast2sms_whatsapp_template_<type>` holding the Meta template *name* (not an ID) per type: `otp`, `registration_pending`, `registration_confirmed`, `registration_denied`, `visit_rescheduled`, `visit_details_changed`. Blank = unconfigured, checked per call like SMS. The API key is shared with SMS (`fast2sms_api_key`); the SMS sender ID is not used. Variable order mirrors Decision 5, and WhatsApp has no 30-char limit so variables are only stringified and newline-collapsed. WhatsApp template bodies are registered with `{{1}}`, `{{2}}` placeholders in that variable order; the template text can reuse the Decision 5 wording.
11. **Contact-method widening**: `ContactMethod` gains `whatsapp`; `_require_contact_for_method` requires a phone for it exactly as for `sms`. `tasks.py::_dispatch` becomes a three-way branch on `primary_contact_preferred_contact_method` (`email` / `sms` / `whatsapp`) and the five tasks pass SMS and WhatsApp template + variables side by side (one shared variable list per event, since the variables are identical). Because `ContactMethod` values are used in prefill/read schemas, those return `whatsapp` automatically. Forms that enumerate allowed contact methods (form_builder defaults) are checked during implementation and updated if they hard-code `email`/`sms`.
12. **OTP over WhatsApp**: `identity_verification/senders.py` replaces `UnconfiguredWhatsAppSender` with the shared WhatsApp sender; `service.py` sends `WhatsAppTemplate.otp` with `[code]`, and the existing non-cached 503-on-failure behaviour applies unchanged.

## Risks / Trade-offs

- DLT template text mismatch (Fast2SMS accepts the request but the operator drops the SMS) → templates in Decision 5 must be registered verbatim; the task list includes an end-to-end check with a real number. Fast2SMS accepting a request does not prove delivery.
- Fast2SMS charges per request including failures and has no documented error codes → log response message; no automatic retry on `return: false` with a 4xx, only on timeouts/5xx.
- Retries can double-send (Celery at-least-once) → SMS is not idempotent; accepted, same as email today, and OTP is deduped by the existing `Idempotency-Key` handling.
- Removing Twilio is breaking for any deployment already configured with it → none documented as live (invitation SMS never worked); note it in the PR.
- Truncating variables to 30 chars can clip a denial reason → acceptable; full reason remains in the tracking page/email.

- WhatsApp template not approved by Meta, or sent to a number that has not opted in → Fast2SMS may accept then fail asynchronously; the six WhatsApp templates must be approved first and consent is already captured at registration. Business-initiated messages are only allowed via templates, hence the no-free-text rule.
- WhatsApp error responses are undocumented → treat anything other than 200 with a message id as failure and log the body.
- Enum widening is additive, but an older client that sends `whatsapp` before the API deploys gets a validation error → deploy API first.

## Migration Plan

1. Register sender ID and the six templates on DLT; obtain Fast2SMS API key. Set up the WhatsApp business number in Fast2SMS and get the six WhatsApp templates approved; note the phone number ID.
2. Deploy code with new env vars (`FAST2SMS_*`); `uv sync` drops `twilio`.
3. Smoke-test OTP over `sms` and `whatsapp` and one invitation SMS and WhatsApp to a real number.
4. Rollback: revert the deploy; no data migration involved.
