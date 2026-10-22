## Why

A visitor whose preferred contact method is `sms` receives the approval notification as a text message, which cannot carry a scannable QR image. Today they get only the tracking ID, and the public tracking-ID endpoint can check in but not check out, so there is no complete SMS-only path through the gate. Visitors on SMS should get a short code in the message that works for both check-in and check-out.

## What Changes

- When an invitation is approved and its primary contact's `preferredContactMethod` is `sms`, generate a numeric check-in code (8 digits, unique per tenant) and send it in the approval SMS instead of any QR reference.
- Add public, unauthenticated check-in and check-out endpoints keyed by that code (`PATCH /api/v2/invitations/code/check-in` and `.../code/check-out`, code in the JSON body so it never lands in URL logs). Both reuse the same eligibility rules and side effects as the QR endpoints (status, expiry, "too early", watchlist, host push, audit log).
- Add brute-force protection: per-IP rate limit plus a per-tenant failed-attempt lockout, and uniform "invalid code" responses.
- Add a DLT SMS template for "approved, with check-in code" and its `FAST2SMS_TEMPLATE_*` setting.
- QR check-in/check-out, badge QR and email/WhatsApp delivery are unchanged. SMS visitors simply stop being sent a QR; the QR endpoints keep working for staff and kiosk use.
- Add a nullable `checkin_code` column on invitations (tenant-schema migration).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `invitations`: adds the SMS check-in code (issuance, delivery, public check-in/check-out by code, abuse protection).

## Impact

- Code: `invitations/models.py`, `repository.py`, `service.py`, `router.py`, `schemas.py`, `tasks.py` (`_send_approval_notification` SMS branch), `core/sms.py` (`SmsTemplate`), `core/config.py`, `.env.example`, new `alembic_tenant` migration.
- API: additive only (new endpoints, no change to existing contracts), so it ships in the existing version.
- Depends on the in-flight `integrate-fast2sms-dlt-sms` change (SMS sender and `preferredContactMethod: sms` delivery).
- Ops prerequisite: a new DLT template must be registered and approved before the template ID is configured.
- Docs: update `docs/features/invitations.md`.
