## Context

Approval already enqueues `send_approval_notification`, which builds an email with a QR and an SMS through the Fast2SMS DLT sender (`integrate-fast2sms-dlt-sms`). The SMS today carries only the tracking ID (`registration_confirmed`). Public check-in exists by encrypted QR token (check-in and check-out) and by tracking ID (check-in only). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A complete SMS-only entry and exit path using one short code.
- Reuse existing check-in/out business rules rather than copying them.

**Non-Goals:**
- Codes for email/WhatsApp contacts, or a code resend endpoint.
- Changing QR, badge or tracking-ID endpoints.
- Per-visitor codes for co-visitors; the code identifies the invitation, as the QR does.

## Decisions

1. **Storage: nullable `checkin_code` String(8) on `invitations`, unique index.** Generated with `secrets.randbelow(10**8)` zero-padded, retried on conflict (same shape as `_generate_unique_tracking_id`). Stored plain, not hashed, because the lookup is by exact value and a reminder SMS may need it again. Alternative considered: a column on `InvitationQRCode`; rejected because SMS invitations have no QR row.
2. **Issue point: in the approval path next to `_issue_qr_code`,** only when the contact method is `sms`, get-or-create so redelivery and the existing idempotency guarantees hold. The QR is still generated for the badge and email-less fallbacks.
3. **Code in the request body, not the path.** Keeps the secret out of access logs and reverse-proxy logs. Endpoints: `PATCH /api/v2/invitations/code/check-in` and `/code/check-out`, in the existing public `router_v2`, using the same default-tenant dependencies as the tracking-ID endpoint.
4. **Reuse via shared helpers.** Extract the post-lookup logic of `check_in_by_qr_token` / `check_out_by_qr_token` into helpers taking an already-resolved `Invitation`, and have the QR path and the code path both call them. Only invitation resolution differs. Invalid codes fold into the same generic 400 style as invalid QR tokens.
5. **Brute-force defence.** 8 digits is 10^8 values, far weaker than a Fernet token, so rate limiting is mandatory. `slowapi` limit (e.g. `10/minute`) per IP, plus a Redis failure counter keyed `vmss:{tenant_id}:invitations:code_fail:{ip}` with a lockout (e.g. 10 failures per 15 minutes) that returns 429 before any lookup. Counter is incremented only on failed lookups. Alternative: lock per invitation; not possible because the attacker does not know the invitation.
6. **SMS template.** New `SmsTemplate.registration_confirmed_code` with variables `[tracking_id, code]` and setting `fast2sms_template_registration_confirmed_code`. The `sms` branch of `_send_approval_notification` uses it when a code exists; the existing template remains for non-SMS paths. Template wording is a DLT registration deliverable, drafted in tasks.
7. **Idempotency.** Both endpoints accept `Idempotency-Key` like the tracking-ID endpoint; the cache key must not contain the code (use the header key only).

## Risks / Trade-offs

- [Code guessing] → rate limit, lockout, 8 digits, generic errors, and code only usable on approved, unexpired, in-window invitations.
- [Plaintext code at rest] → it grants only check-in/out for one visit, expiring with the invitation; PII is not exposed by the response beyond what QR check-in already returns. Revisit if the response is ever trimmed.
- [Redis unavailable] → fail closed on the lockout check (429/503), not open.
- [New DLT template approval delay] → feature is inert until the template ID is configured; not-configured is a non-retried error, so approval is unaffected.
- [Code shared or forwarded] → same exposure as a forwarded QR.

## Migration Plan

Add the tenant migration (nullable column, unique index) and apply it to all tenant schemas. Existing invitations have no code and are unaffected. Deploy code, register and configure the DLT template. Rollback: ignore the column; endpoints return invalid code for everything.
