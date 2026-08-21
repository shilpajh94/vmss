## Why

The visitor portal's "Request a Visit" flow (Figma: `visitor-portal-landing.pdf`
→ mobile/email entry → "Request OTP") requires proving a visitor controls the
contact channel they submit before they're allowed to fill in the full
registration wizard. `docs/features/registrations.md` and
`security-architecture.md` §2 already flag this as a required, tracked gap —
"no OTP mechanism exists anywhere in this codebase yet." API-15 closes that
gap: a visitor supplies an email or phone number, receives a one-time code
over their chosen channel, and proves control of it before proceeding.

## What Changes

- New public, unauthenticated endpoint to request an OTP for an email or
  phone identifier, delivered over the caller's chosen channel (email, SMS,
  or WhatsApp).
- New public, unauthenticated endpoint to verify a submitted OTP against the
  identifier it was issued for, returning a short-lived signed
  "verified-contact" proof token the caller can present later.
- OTP codes are single-use, short-expiry (5 minutes), rate-limited per
  identifier and per IP, and invalidated after a fixed number of failed
  verify attempts — per `security-architecture.md` §2's OTP handling rules.
  Codes and full identifiers are never logged in plaintext
  (`logging-observability.md` §2).
- OTP state lives in Redis only (`vmss:{tenant_id}:identity-verification:...`
  keys, `database-architecture.md` §6) — no new Postgres table, since an OTP
  attempt has no durable audit/business value once it expires or is consumed.
- New `EmailSender`/`SmsSender`/`WhatsAppSender` provider interfaces
  (mirroring the pattern `invitations/notifications.py` already established
  for email/SMS). Email delivery is real (reuses the existing SMTP sender).
  SMS delivery is also real, via Twilio — the only channel of the three
  with an actual chosen provider. WhatsApp still ships as an
  `UnconfiguredWhatsAppSender` placeholder that raises loudly rather than
  pretend to send — no WhatsApp gateway has been chosen yet. Wiring a real
  WhatsApp gateway is a flagged follow-up once a provider is chosen, not
  part of this change. If Twilio credentials are absent in a given
  deployment (e.g. local dev without `.env` secrets), SMS falls back to the
  same loud "unconfigured" behavior rather than crashing at startup.
- **Not in scope for this change**: gating `POST /invitations` or `POST
  /registrations/walk-in` on a verified-contact proof. This change ships the
  request/verify endpoints and the proof token only; wiring that proof into
  the existing invitation/registration creation contracts is a separate,
  later change (avoids a breaking change to two already-shipped endpoints
  bundled with this one).

## Capabilities

### New Capabilities
- `identity-verification`: OTP generation and verification for an
  email/phone identifier, over email/SMS/WhatsApp, producing a short-lived
  verified-contact proof.

### Modified Capabilities
(none — existing `invitations`/`registrations` contracts are unchanged by
this change; see "Not in scope" above)

## Impact

- **New code**: `src/vmss_api/identity_verification/` (`router.py`,
  `service.py`, `schemas.py`, `senders.py`, `tests.py`) — no `models.py`/
  `repository.py`, since state is Redis-only, not Postgres.
- **Registered in**: `src/vmss_api/api.py` (router), `src/vmss_api/main.py`
  (`openapi_tags` entry per `api-documentation.md` §2).
- **Config**: new `.env.example` placeholders for OTP TTL/length, Twilio
  credentials (`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/
  `TWILIO_SMS_FROM_NUMBER`), and WhatsApp gateway base URL/API key
  (mirroring the existing unset `SMS_GATEWAY_*` placeholders, which this
  feature does not reuse — see design.md's Senders decision).
- **Dependencies**: reuses existing `redis.asyncio`, `slowapi` (rate
  limiting), `aiosmtplib` (email); adds `twilio` (official SDK, via
  `uv add twilio`) for SMS.
- **Tenant resolution**: this is a public, portal-facing endpoint with no
  bearer token, so it resolves the single configured `default_tenant_slug`
  the same way `GET /invitations/track` does
  (`invitations/deps.py::track_default_tenant_db`) — a known limitation to
  replace with real hostname-based tenant routing once a second tenant
  exists, not a new one introduced by this change.
