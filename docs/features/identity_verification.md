# Identity Verification (OTP)

Lets an unauthenticated visitor prove they control an email address or
phone number — API-15 — by requesting a one-time code and submitting it
back, before that contact is trusted anywhere downstream in the
visitor-facing registration flow. Closes the gap `docs/features/
registrations.md` and `security-architecture.md` §2 both flagged: "no OTP
mechanism exists anywhere in this codebase yet." See
`openspec/changes/add-identity-verification-otp/` for the proposal/design
this feature was built from.

`identity_verification` owns no Postgres table — OTP state lives in Redis
only (`vmss:{tenant_id}:identity-verification:...` keys), since a code has
no durable audit/business value once it expires or is consumed.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| POST | `/api/v1/identity-verification/otp/request` | None (public) | 20/minute per IP, plus a per-identifier limit (`OTP_RATE_LIMIT_PER_IDENTIFIER` per `OTP_RATE_LIMIT_WINDOW_SECONDS`) | Generates a one-time code for an `identifier` (email or phone) and dispatches it over the requested `channel` (`email`, `sms`, or `whatsapp`). Returns an ack (`identifier`, `channel`) — never the code itself. Accepts an optional `Idempotency-Key` header. |
| POST | `/api/v1/identity-verification/otp/verify` | None (public) | 20/minute per IP | Verifies a submitted `code` against the identifier it was issued for. On success, returns a short-lived signed `proofToken` (15 minutes) proving the identifier was verified. Accepts an optional `Idempotency-Key` header. |

## Channels and senders

| Channel | Status | Provider |
|---|---|---|
| `email` | Real | SMTP, via the same `aiosmtplib`/`settings.smtp_*` config `invitations` uses. |
| `sms` | Real, if configured | Twilio (`TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_SMS_FROM_NUMBER`). Falls back to a loud "not configured" error if any of the three is unset — never a false success. |
| `whatsapp` | Not implemented | No provider chosen yet; every request over this channel returns a 503. |

`identity_verification/senders.py` defines its own `EmailSender`/
`SmsSender`/`WhatsAppSender` abstractions — deliberately not shared with
`invitations/notifications.py`'s near-identical ones yet (see design.md's
Non-Goals on why that extraction is a separate, later change).

### Twilio trial-account restriction

A Twilio **trial** account (the default before the account is upgraded to
paid) can only send SMS to phone numbers that have been individually
verified in the Twilio console. Until the account is upgraded, SMS to any
other number will fail at the Twilio API level — surfaced here as the same
generic 503 a Twilio outage would produce, not a distinct error, since the
client-facing response never carries Twilio-specific detail
(`security-architecture.md` §4). Check the Twilio console/error logs
server-side if SMS unexpectedly fails in a fresh deployment.

## OTP lifecycle

- **Expiry**: `OTP_TTL_SECONDS` (default 300 — 5 minutes), enforced by
  Redis's own key TTL.
- **Single-use**: a successfully verified code is deleted immediately.
- **Superseding**: requesting a new code for the same identifier
  overwrites the previous one — at most one valid code per identifier at a
  time.
- **Failed attempts**: capped at `OTP_MAX_ATTEMPTS` (default 5) consecutive
  wrong guesses per issued code; exceeding it invalidates the code
  entirely, including the originally-correct one.
- **Verified-contact proof**: `core/security.py::create_identity_verified_token`
  issues a JWT with `sub` set to the identifier itself (not a UUID — so an
  access/refresh-token consumer expecting a UUID `sub` fails to parse it
  rather than mistaking this for a session token), `type:
  "identity_verified"`, and a `channel` claim. **No caller in this
  codebase consumes this token yet** — see "Not yet built" below.

## Idempotency

Both endpoints accept an `Idempotency-Key` header (`api-conventions.md`
§3), cached in Redis for 24h, same pattern `invitations` already uses for
`POST /invitations`. One refinement for the request endpoint: only a
*definitive* outcome is cached (success, a validation error, or a
gateway-not-configured error) — a *transient* SMS dispatch failure (a
Twilio-side error while properly configured) is deliberately **not**
cached, so a retry with the same key re-attempts dispatch instead of
replaying the same transient failure forever.

## Dispatch failure diagnostics

`senders.py::SmtpEmailSender.send` logs `smtp_email_dispatch_failed` at
`WARNING` when the configured SMTP gateway rejects or fails to send an OTP
email (`fix-public-org-listings-and-email-diagnostics`). Alongside the
existing masked `identifier` and `error` fields, the log line now also
carries `smtp_host`, `smtp_port`, and `exception_type` — enough to
root-cause a deployment-specific failure (e.g. "works against the local
Mailpit catcher but fails on a given server") from logs alone, without
reproducing it locally. Never logged: SMTP credentials, or the OTP code
itself. The client-facing response is unchanged — still a generic 503
`"This delivery channel is temporarily unavailable"`, no gateway detail.

## Tenant resolution

Like `GET /invitations/track`, these endpoints carry no bearer token and
no tenant identifier, so they resolve the single configured
`settings.default_tenant_slug` tenant via the shared
`core.tenancy.resolve_default_tenant` (`identity_verification/deps.py::
default_tenant_id`) — a known limitation to replace with real
hostname-based tenant routing once a second tenant exists. If that tenant
doesn't exist or is inactive, this is a server-side misconfiguration, not a
caller error: it's logged at `ERROR` as
`identity_verification_default_tenant_unconfigured`, distinguishing "no
such tenant" from "tenant inactive" so an operator can tell the fix from
the log alone, consistent with `registrations`' equivalent fallback
(`docs/features/registrations.md`). The client-facing response is
unchanged — still 404 `"Tenant not found or inactive"`.

## Config knobs

| Setting | Default | Purpose |
|---|---|---|
| `OTP_TTL_SECONDS` | `300` | How long a generated code stays valid. |
| `OTP_LENGTH` | `6` | Digits in a generated code. |
| `OTP_MAX_ATTEMPTS` | `5` | Consecutive wrong guesses allowed per code before it's invalidated. |
| `OTP_RATE_LIMIT_PER_IDENTIFIER` | `5` | Max OTP requests per identifier within the rate-limit window. |
| `OTP_RATE_LIMIT_WINDOW_SECONDS` | `3600` | Window for the per-identifier rate limit. |
| `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_SMS_FROM_NUMBER` | unset | Required for real SMS delivery. Leave unset to keep SMS in its loud "not configured" state. |
| `WHATSAPP_GATEWAY_BASE_URL`/`WHATSAPP_GATEWAY_API_KEY` | unset | Placeholders — no WhatsApp gateway has been chosen yet. |

## Not yet built (flagged, not silently dropped)

- **WhatsApp delivery.** No provider chosen; every `whatsapp`-channel
  request returns 503.
- **Gating `POST /invitations` / `POST /registrations/walk-in` on a
  verified-contact proof.** This feature produces the `proofToken`; no
  endpoint in this codebase requires or consumes it yet. Wiring that gate
  into invitation/walk-in-registration creation is a separate, later
  change — deliberately kept out of this one to avoid a breaking change to
  two already-shipped endpoints bundled with a new, unrelated feature.
- **Shared `notifications/` package.** `identity_verification` and
  `invitations` now each have their own near-identical email/SMS sender
  abstractions. Extracting a shared package is tracked as a deliberate,
  deferred decision (design.md's Non-Goals), not an oversight.
