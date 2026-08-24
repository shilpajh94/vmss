## Context

See `proposal.md` - Why. Relevant existing state:

- `invitations/notifications.py` already defines an `EmailSender`/`SmsSender`
  `Protocol` pair with a real `SmtpEmailSender` and a loud
  `UnconfiguredSmsSender`, deliberately scoped as "not the general
  multi-channel `notifications/` package... built once a second feature
  needs it." This change is that second feature.
- `invitations/deps.py::track_default_tenant_db` is the existing pattern for
  a public, tokenless endpoint resolving the single configured
  `default_tenant_slug` tenant.
- `core/security.py::_create_token`/`decode_token` is the existing JWT
  helper, currently only used for user/superadmin subjects with a UUID
  `sub` claim.
- `core/rate_limit.py::limiter` (slowapi, Redis-backed) is keyed by remote
  address only today; nothing in the codebase yet rate-limits by an
  arbitrary request field (identifier).
- SMS now targets Twilio (chosen for this feature specifically - no
  vendor preference was given, Twilio is a mainstream, well-documented
  default). No WhatsApp gateway has been selected (open product/infra
  decision, unchanged). The existing `SMS_GATEWAY_BASE_URL`/
  `SMS_GATEWAY_API_KEY` placeholders in `.env.example` belong to
  `invitations`' still-unbuilt SMS integration (unused even by today's
  `UnconfiguredSmsSender`, which raises unconditionally without reading
  them) - this feature does not reuse or repurpose them, per the Senders
  decision below.

## Goals / Non-Goals

**Goals:**
- Working OTP request/verify over email (real SMTP send) and over SMS
  (real Twilio send) today.
- A clean channel abstraction (`email`/`sms`/`whatsapp`) so wiring a real
  WhatsApp gateway later is a new sender implementation, not a call-site or
  contract change.
- Redis-only state - no new Postgres table or migration for a 5-minute-lived
  code.

**Non-Goals:**
- Choosing or integrating a WhatsApp provider (per the proposal's "Not in
  scope" - SMS now has a chosen provider, Twilio; WhatsApp still doesn't).
- Gating `POST /invitations` or `POST /registrations/walk-in` on the
  verified-contact proof this change introduces (per the proposal's "Not in
  scope") - the proof token's shape is designed to be consumable by a later
  change, but nothing here calls it.
- Extracting `invitations/notifications.py`'s senders into a shared
  top-level `notifications/` package. Two features now have near-identical
  `EmailSender`/`SmsSender` protocols, which is the trigger condition
  `invitations/notifications.py`'s own docstring names for building that
  shared package - but doing so means refactoring `invitations` inside a
  change scoped to a new, unrelated feature. Deferred to its own change so
  it can be reviewed (and rolled back) independently; tracked as a known
  duplication, not an oversight.

## Decisions

### New standalone feature package, Redis-only
`src/vmss_api/identity_verification/` gets `router.py`, `service.py`,
`schemas.py`, `senders.py`, `deps.py`, `tests.py` - no `models.py`/
`repository.py`. An OTP attempt has no durable audit/business value once it
expires or is consumed (unlike a check-in or an invitation), so it doesn't
belong in `AuditLog` or any Postgres table; Redis's own TTL does the
cleanup. This also sidesteps a tenant-schema migration for a purely
ephemeral concept.

### Redis key shape and stored fields
Key: `vmss:{tenant_id}:identity-verification:otp:{channel}:{identifier}`.
One key holds a small hash: `code_hash`, `attempts_remaining`, `issued_at`.
TTL on the key is exactly the OTP expiry window (5 minutes), so an expired
code is simply absent rather than needing an explicit expiry check -
Redis's own eviction is the expiry mechanism, not application logic
re-checking a timestamp.

**Why hash the code at rest, not store it plaintext**: even a short-lived,
low-entropy 6-digit code shouldn't sit in plaintext in a store other
processes (ops tooling, a Redis GUI, a future logging integration) might be
able to read - `logging-observability.md` §2's "never log OTP in plaintext"
rule extends naturally to "never store it in plaintext" for the same
reason. HMAC-SHA256 with a server-side secret (not Argon2 - a numeric code
has far less entropy than a password and the failed-attempt cap plus rate
limiting, not hash cost, is what actually blocks brute force here; Argon2's
deliberate slowness would only add latency for no real security gain on a
6-digit space) keyed off `settings.jwt_secret_key` (reusing the existing
secret rather than introducing a second one to manage).

**Alternative considered**: a Postgres table with a partial index on
non-expired rows. Rejected - it's a durable store for data whose entire
value disappears in 5 minutes, plus a migration for no future need
(nothing here or planned reads OTP history after the fact).

### Requesting a new code invalidates the previous one
`SETEX`-style overwrite of the same key on a fresh request naturally
achieves "at most one valid code per identifier" (spec's superseding
requirement) - no separate invalidation step needed, since writing the new
hash simply replaces whatever was there.

### Per-identifier rate limiting is a service-layer Redis counter, not slowapi
`core/rate_limit.py::limiter` already rate-limits by IP via a decorator on
the route. The spec also requires limiting by identifier (an attacker
rotating source IPs must not be able to bomb one phone number/email
indefinitely). Since slowapi's key function is fixed per-limiter to "the
request," identifier-based limiting is a small explicit Redis `INCR` +
`EXPIRE` counter in `service.py` (key:
`vmss:{tenant_id}:identity-verification:rl:{channel}:{identifier}`),
checked before generating a code, raising the same 429 the IP-based limiter
would. This is deliberately hand-rolled rather than a second slowapi
instance, since slowapi has no clean per-field key hook without reaching
into its internals.

### Verified-contact proof token
A new `core/security.py` function, `create_identity_verified_token(
identifier: str, channel: str, tenant_id: uuid.UUID) -> str`, alongside the
existing `_create_token` helper - `sub` is the identifier (not a UUID, so it
can't be reused as a real access/refresh token: `decode_token` callers that
expect a UUID `sub` will fail to parse it, which is the desired failure
mode for "this proof must never be mistaken for a session token"), `type:
"identity_verified"`, a 15-minute expiry (long enough to finish filling out
the registration wizard after verifying, short enough that a leaked proof
has a small window), and `channel`/`tenant_id` claims. No new
`decode_identity_verified_token` consumer exists yet - it's produced, not
yet consumed, per the proposal's deferred-integration decision; the shape
is designed for a later change to consume by branching on `type` the same
way `decode_token` callers already do for `"access"` vs `"refresh"`.

### Senders: real email, real SMS via Twilio, unconfigured WhatsApp
`identity_verification/senders.py` defines its own `EmailSender`/
`SmsSender`/`WhatsAppSender` `Protocol`s (mirroring, not importing,
`invitations/notifications.py` - see Non-Goals). `EmailSender` gets a real
`SmtpEmailSender` (same `aiosmtplib`/`settings.smtp_*` config already used
by `invitations`). `WhatsAppSender` gets an `UnconfiguredWhatsAppSender`
that raises a `GatewayNotConfiguredError` - the service layer catches this
and returns `error_response` with a 503, matching the spec's "fails loudly"
requirement. New `.env.example` placeholders: `WHATSAPP_GATEWAY_BASE_URL`,
`WHATSAPP_GATEWAY_API_KEY` (mirroring the existing unset `SMS_GATEWAY_*`
pair, though unused by this feature - see Context).

**`SmsSender` gets a real `TwilioSmsSender`.** New settings:
`twilio_account_sid`, `twilio_auth_token`, `twilio_sms_from_number` (E.164
format). At module load, `identity_verification/senders.py` picks
`TwilioSmsSender` when all three are set, otherwise falls back to the same
`UnconfiguredSmsSender` shape `WhatsAppSender` uses - so a dev/test
environment with no Twilio secrets in `.env` behaves exactly like today
(loud 503, not a startup crash from constructing a Twilio client with empty
credentials).

- **Library choice**: the official `twilio` PyPI SDK
  (`uv add twilio`), not a hand-rolled `httpx` call against Twilio's REST
  API. *Alternative considered*: raw HTTP (Basic Auth + form-encoded POST
  to `https://api.twilio.com/.../Messages.json`) to avoid a new dependency
  - rejected because the SDK's typed exceptions
  (`twilio.base.exceptions.TwilioRestException`, carrying a numeric Twilio
  error code) are more reliable to branch on than hand-parsing Twilio's
  JSON error body, and Twilio's API surface/auth details are exactly the
  kind of thing a maintained SDK insulates this codebase from changing
  under it.
- **Blocking call, async handler**: the SDK's `Client.messages.create(...)`
  is synchronous (blocking network I/O), so `TwilioSmsSender.send` wraps it
  in `anyio.to_thread.run_sync` (`fastapi-architecture.md` §4 - the same
  pattern used for any blocking call from an `async def` path), rather than
  blocking the event loop for the duration of the Twilio round-trip.
- **Error mapping**: `TwilioSmsSender.send` catches `TwilioRestException`
  and re-raises it as the same kind of dispatch failure
  `UnconfiguredSmsSender` raises today (a single `SmsDispatchError` the
  service layer already knows how to turn into a 503) - the public,
  unauthenticated verify-identity endpoint never surfaces Twilio's raw
  error code/message to the caller (`security-architecture.md` §4:
  generic client-facing errors, no vendor/internal detail). The Twilio
  error code and message are still logged server-side at `WARNING`
  (`logging-observability.md` §3) so an operator can diagnose e.g. an
  exhausted Twilio balance or an unverified trial-account destination
  number without that detail ever reaching the visitor.
- **No inline retry**: a single synchronous attempt per request - this is
  a request-path call the visitor is actively waiting on (unlike
  `invitations`' fire-and-forget Celery-dispatched confirmation email), so
  retrying inline would only extend how long the visitor's HTTP request
  hangs. A visitor whose SMS genuinely failed to send retries by calling
  the request endpoint again (see the Idempotency-Key refinement below for
  why that retry isn't swallowed by the idempotency cache).

### Tenant resolution: a lighter dependency than `track_default_tenant_db`
This feature never touches a tenant-schema Postgres table (Decision:
Redis-only), so it doesn't need `tenant_session_scope`'s tenant-bound
session - only the tenant's `id` (for the Redis key namespace,
`database-architecture.md` §6). New `identity_verification/deps.py::
default_tenant_id` depends on `get_db` (global schema only) and
`TenantRepository.get_by_slug(settings.default_tenant_slug)`, returning
just the UUID. Same known single-tenant limitation as
`track_default_tenant_db` (flagged, not new to this change) - replace with
real hostname-based routing once a second tenant exists.

### Idempotency-Key handling
Per `api-conventions.md` §3, cache `(idempotency_key, tenant_id) ->
response` in Redis for ~24h, keyed
`vmss:{tenant_id}:identity-verification:idem:{key}`, checked before
generating a code or counting a verify attempt - this is the same pattern
`invitations` already uses for `POST /invitations`, just reused here rather
than newly designed.

**What gets cached, refined for a real gateway**: only a *definitive*
outcome is cached - a successful dispatch, a validation error (bad
identifier/channel), or a gateway-unconfigured error (WhatsApp always;
SMS when Twilio secrets are unset). A *transient* dispatch failure (a
`TwilioRestException` from an SMS send - rate-limited, Twilio-side outage,
temporary account issue) is deliberately **not** cached: it's still
returned as a 503 for that one request, but the next request with the same
`Idempotency-Key` re-attempts dispatch rather than replaying the same
failure forever. Caching every response verbatim (the original,
simpler-gateway-less design) was fine when the only failure mode was
"permanently unconfigured," but a real gateway now has failure modes that
resolve themselves (Twilio recovers) or need a genuinely new attempt - a
visitor whose retry is silently served yesterday's cached 503 would have
no way to ever get their code.

## Risks / Trade-offs

- **[Risk]** Two near-identical sender abstractions (`invitations` and
  `identity_verification`) now exist. → **Mitigation**: documented above as
  a deliberate, tracked duplication; revisit extraction into a shared
  `notifications/` package as its own change once a third consumer appears
  or the two drift in a way that causes a real bug.
- **[Risk]** Hand-rolled per-identifier Redis rate limiting duplicates some
  of what slowapi does for per-IP limiting, so there are now two rate-limit
  code paths to reason about. → **Mitigation**: kept intentionally small
  (one `INCR`/`EXPIRE` pair, no new abstraction layer); revisit if a third
  endpoint needs per-field limiting and a shared helper becomes worth
  building.
- **[Risk]** The verified-contact proof is produced but has no consumer in
  this change, so it can't be exercised end-to-end by a real client until
  the follow-up change lands. → **Mitigation**: `tests.py` verifies the
  token's shape/claims directly (decode and assert `type`/`channel`/
  `identifier`/expiry) rather than only via an integration path that
  doesn't exist yet.
- **[Risk]** WhatsApp remains unusable until a gateway is chosen - visitors
  who only want WhatsApp delivery have no working path today. →
  **Mitigation**: this is an explicit, flagged product/infra decision, not
  a regression; the loud 503 makes the gap visible rather than silently
  discarding the request. Email and SMS both work, so the portal always has
  at least one functioning channel.
- **[Risk]** SMS delivery now depends on a live third-party service
  (Twilio) reachable from the request path - a Twilio outage, an exhausted
  account balance, or a misconfigured `from` number turns into a 503 for
  every SMS-channel OTP request until fixed. → **Mitigation**: failure is
  explicit and logged with the Twilio error code server-side (not swallowed
  as a false success); email remains a fully independent channel unaffected
  by a Twilio-side incident; the Idempotency-Key refinement above ensures a
  visitor can simply retry once the underlying issue clears instead of being
  stuck on a cached failure.
- **[Risk]** The Twilio SDK's synchronous client, if called directly from
  an `async def` route/service function, would block the event loop for
  every concurrent request during the Twilio round-trip. →
  **Mitigation**: `TwilioSmsSender.send` always goes through
  `anyio.to_thread.run_sync` (`fastapi-architecture.md` §4); covered by a
  test asserting the event loop stays responsive during a slow/mocked
  Twilio call (task 9.2 revision).
- **[Risk]** A Twilio trial account (the default before a paid account is
  provisioned) can only send to phone numbers pre-verified in the Twilio
  console, which would silently look like "SMS is broken" in a fresh
  deployment. → **Mitigation**: flagged here explicitly, not discovered the
  hard way - `docs/features/identity_verification.md` (task 10.1) notes the
  trial-account restriction and that upgrading the Twilio account removes
  it.

## Migration Plan

No schema migration (Redis-only). Deploy steps: `uv add twilio` (new
dependency, commit the updated `uv.lock`), ship the new router behind
`api.py`/`main.py` registration, add the new `.env.example` placeholders
(no default Twilio/WhatsApp credentials, so nothing breaks if unset - both
the `UnconfiguredSmsSender` fallback and `UnconfiguredWhatsAppSender`
handle that explicitly). Setting real Twilio credentials in a given
deployment's `.env` is what turns SMS on; nothing else about the deploy
changes. No rollback concerns beyond reverting the deploy - no persisted
state outlives a single OTP's 5-minute TTL.
