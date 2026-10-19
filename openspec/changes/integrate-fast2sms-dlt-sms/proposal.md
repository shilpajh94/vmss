## Why

India's TRAI DLT rules only allow SMS built from pre-registered templates sent under a registered sender ID. Twilio (today's OTP SMS provider) doesn't fit that model, and invitation SMS (approval, denial, reschedule, …) is still an unconfigured stub, so a visitor whose preferred contact method is `sms` currently gets nothing. Fast2SMS's DLT route (`https://docs.fast2sms.com/reference/dlt-sms`) fixes both with one provider. The same provider also offers a WhatsApp Business API, which gives visitors who prefer WhatsApp a working channel: OTP over `whatsapp` is accepted by the API today but has no gateway, and invitations have no WhatsApp option at all.

## What Changes

- Add a Fast2SMS DLT SMS sender: `GET https://www.fast2sms.com/dev/bulkV2` with `route=dlt`, `sender_id`, `message` (the DLT template ID), `variables_values` (`|`-separated), and `numbers`, authenticated by an `Authorization` API-key header.
- SMS is now template-driven: each SMS-sending message type maps to a DLT template ID plus an ordered list of variable values, instead of a free-text body.
- Wire it into every visitor-facing SMS path: identity-verification OTP, and the invitation notifications (registration pending, confirmed with tracking ID, denied, rescheduled, details changed) when `preferredContactMethod` is `sms`.
- Add a Fast2SMS WhatsApp template sender: `POST https://www.fast2sms.com/dev/whatsapp/{version}/{phone_number_id}/messages` with an `Authorization` API-key header, a template name, language code and ordered body variables.
- Add `whatsapp` as a `preferredContactMethod` value (additive, `v1`) and send the same five invitation notifications by WhatsApp for those contacts; make OTP over the existing `whatsapp` channel work.
- Add settings: `FAST2SMS_API_KEY`, `FAST2SMS_SENDER_ID`, one DLT template-ID setting per SMS message type, the WhatsApp phone number ID, API version, language code and one template-name setting per WhatsApp message type; document them in `.env.example`.
- **BREAKING (internal)**: remove Twilio (`twilio_*` settings, `TwilioSmsSender`, the `twilio` dependency) and the unused `sms_gateway_*` placeholders. Replace the `SmsSender.send(to, body)` signature with a template-based one.
- SMS copy is now bounded by the registered DLT templates; the edit-details SMS is shortened to fit a template's variable limits.

## Capabilities

### New Capabilities
- `sms-notifications`: Fast2SMS DLT delivery, template/variable mapping, phone normalisation, configuration, failure behaviour, and visitor SMS for invitation lifecycle events.

- `whatsapp-notifications`: Fast2SMS WhatsApp template delivery, template/variable mapping, phone normalisation, configuration, failure behaviour, and visitor WhatsApp for invitation lifecycle events.

### Modified Capabilities
- `invitations`: `preferredContactMethod` accepts `whatsapp` (phone required).
- `identity-verification`: OTP over `sms` is delivered via Fast2SMS DLT instead of Twilio, and over `whatsapp` via the Fast2SMS WhatsApp authentication template (dispatch-failure logging and "SMS text unchanged" requirements updated).

## Impact

- Code: `identity_verification/senders.py`, `identity_verification/service.py`, `invitations/notifications.py`, `invitations/tasks.py` (`_dispatch` + the five `sms_body` builders), `invitations/schemas.py` (`ContactMethod`), `core/whatsapp.py` (new), `core/config.py`, `.env.example`, `pyproject.toml`/`uv.lock` (drop `twilio`; HTTP via existing/`httpx`), existing tests that import `TwilioSmsSender`.
- External: requires a Fast2SMS account, DLT-registered sender ID and approved templates (ops/prerequisite, not code).
- No DB or migration changes (`primary_contact_preferred_contact_method` is `String(10)`, `whatsapp` fits). API contract: additive only, `preferredContactMethod` gains `whatsapp`; OTP `channel` values unchanged.
- External: Fast2SMS WhatsApp Business setup (WABA, phone number ID) and Meta-approved templates.
