## 1. Config

- [x] 1.1 Add `otp_ttl_seconds` (default `300`), `otp_length` (default `6`),
      `otp_max_attempts` (default `5`), `otp_rate_limit_per_identifier` and
      `otp_rate_limit_window_seconds` settings to `core/config.py`.
- [x] 1.2 Add `whatsapp_gateway_base_url`/`whatsapp_gateway_api_key`
      settings to `core/config.py` (unconfigured placeholder, unchanged
      from the original design).
- [x] 1.3 Add `twilio_account_sid`/`twilio_auth_token`/
      `twilio_sms_from_number` settings to `core/config.py` for the real
      SMS integration (design.md "Senders" decision) — distinct from, and
      not reusing, the existing unused `sms_gateway_base_url`/
      `sms_gateway_api_key` placeholders.
- [x] 1.4 Add `uv add twilio` to the project's dependencies (new
      third-party SDK, per design.md's library-choice decision).
- [x] 1.5 Add all new settings to `.env.example` (unset/default, per
      `security-architecture.md` §3).

## 2. Feature scaffold

- [x] 2.1 Create `src/vmss_api/identity_verification/` with `__init__.py`,
      `router.py`, `service.py`, `schemas.py`, `senders.py`, `deps.py`,
      `tests.py`.
- [x] 2.2 Define `Channel` enum (`email`, `sms`, `whatsapp`) and request/
      response `CamelModel` schemas in `schemas.py`: `OtpRequestIn`
      (identifier, channel), `OtpRequestOut` (ack only, no code),
      `OtpVerifyIn` (identifier, channel, code), `OtpVerifyOut` (proof
      token, identifier, channel). Validate identifier format against
      channel per the spec's "identifier does not match channel" scenario.

## 3. Senders (design.md "Senders" decision)

- [x] 3.1 Define `EmailSender`/`SmsSender`/`WhatsAppSender` `Protocol`s in
      `senders.py`.
- [x] 3.2 Implement `SmtpEmailSender` (reuse `settings.smtp_*`, same
      `aiosmtplib` approach as `invitations/notifications.py`).
- [x] 3.3 Implement `GatewayNotConfiguredError`, `SmsDispatchError`, and
      `UnconfiguredWhatsAppSender` (always raises
      `GatewayNotConfiguredError` — no real WhatsApp integration in this
      change).
- [x] 3.4 Implement `TwilioSmsSender`: construct a `twilio.rest.Client`
      from `settings.twilio_account_sid`/`twilio_auth_token`; `send()`
      calls `client.messages.create(to=identifier,
      from_=settings.twilio_sms_from_number, body=...)` via
      `anyio.to_thread.run_sync` (blocking SDK call, per
      `fastapi-architecture.md` §4); catch
      `twilio.base.exceptions.TwilioRestException`, log the Twilio error
      code/message at `WARNING`, and re-raise as `SmsDispatchError` (no
      Twilio-specific detail crosses into the client-facing error).
- [x] 3.5 Implement `UnconfiguredSmsSender` (same shape as
      `UnconfiguredWhatsAppSender`) as the fallback when Twilio settings
      are incomplete.
- [x] 3.6 Module-level `email_sender`/`whatsapp_sender` instances plus a
      `sms_sender` selected at module load: `TwilioSmsSender` when all
      three Twilio settings are present, otherwise `UnconfiguredSmsSender`
      (design.md's fallback decision — no startup crash from empty
      credentials).

## 4. Core security helper

- [x] 4.1 Add `create_identity_verified_token(identifier, channel,
      tenant_id) -> str` to `core/security.py`, using the existing
      `_create_token` helper with `sub=identifier`, `type:
      "identity_verified"`, a 15-minute expiry, and a `channel` claim
      (design.md "Verified-contact proof token").

## 5. Tenant resolution

- [x] 5.1 Add `identity_verification/deps.py::default_tenant_id`,
      resolving `settings.default_tenant_slug` via `TenantRepository` on a
      plain `get_db` session and returning the tenant's id (404 if missing/
      inactive) — no tenant-schema session needed (design.md decision).

## 6. OTP service logic (Redis-only state)

- [x] 6.1 Implement `service.py::request_otp`: per-identifier rate-limit
      check (Redis `INCR`/`EXPIRE`), generate a numeric code of
      `settings.otp_length`, store `{code_hash, attempts_remaining}` at
      `vmss:{tenant_id}:identity-verification:otp:{channel}:{identifier}`
      with TTL `settings.otp_ttl_seconds` (overwrite supersedes any prior
      code), dispatch via the channel's sender. (Idempotency-Key
      check/short-circuit and the cache-only-definitive-outcomes rule are
      implemented in `router.py`, mirroring `invitations/router.py`'s
      existing idempotency-cache pattern rather than duplicating it inside
      `service.py` — same behavior as designed, different layer, so the
      router can decide caching per exception type raised here.)
- [x] 6.2 Implement `service.py::verify_otp`: look up the Redis entry,
      reject if absent (expired/never requested) or if
      `attempts_remaining <= 0`, compare `HMAC-SHA256(code)` against
      `code_hash`; on mismatch decrement `attempts_remaining` and raise a
      generic failure; on match delete the Redis key (single-use) and
      return a success result. Idempotency-Key handling lives in
      `router.py` (see 6.1's note) and caches both success and failure for
      verify, per the spec's replay requirement.
- [x] 6.3 On successful verification, call
      `create_identity_verified_token` and return it in the result.
- [x] 6.4 `router.py` wraps both `GatewayNotConfiguredError` (WhatsApp
      always; SMS when Twilio settings are incomplete) and
      `SmsDispatchError` (a configured Twilio call that failed) into a 503
      `error_response` with a generic message — no Twilio error code/
      message reaches the response body (`security-architecture.md` §4),
      per the spec's "fails loudly" requirement. Only the
      `GatewayNotConfiguredError` response is cached under the
      `Idempotency-Key`; `SmsDispatchError` (transient) is not.
- [x] 6.5 Ensure no code, code hash, or unmasked identifier is included in
      any raised exception message or `structlog` call — mask the
      identifier (first char + domain for email, last 2 digits for phone)
      in all log lines (`logging-observability.md` §2).

## 7. Router

- [x] 7.1 `POST /api/v1/identity-verification/otp/request` — public, no
      auth, `slowapi`-rate-limited per IP (per
      `security-architecture.md` §2), accepts `Idempotency-Key` header,
      calls `service.request_otp`, returns `success_response` with
      `response_model=Envelope[OtpRequestOut]`.
- [x] 7.2 `POST /api/v1/identity-verification/otp/verify` — same posture,
      calls `service.verify_otp`, returns `success_response` with
      `response_model=Envelope[OtpVerifyOut]`.
- [x] 7.3 Register the router in `src/vmss_api/api.py`
      (`fastapi-architecture.md` §7).
- [x] 7.4 Add the `identity-verification` tag with a description to
      `_TAGS_METADATA` in `main.py` (`api-documentation.md` §2).

## 8. Logging

- [x] 8.1 Bind `request_id`/`tenant_id` (no `user_id` — unauthenticated) at
      the top of both endpoints per `logging-observability.md` §1, and log
      OTP request/verify outcomes at `INFO` (success) / `WARNING`
      (failure, rate-limit trip) with the masked identifier only.

## 9. Tests (`identity_verification/tests.py`)

- [x] 9.1 Happy path: request OTP over email, verify with the correct code
      (read the code via a test hook/fixture that inspects Redis directly,
      since it's never in the response), assert a valid
      `identity_verified` proof token is returned with correct claims.
- [x] 9.2a Happy path: request OTP over `sms` with a mocked Twilio client
      (patch/stub the `twilio.rest.Client` used by `TwilioSmsSender` —
      mocking a third-party HTTP API is unrelated to
      `testing-standards.md`'s real-Postgres rule, which is DB-specific)
      succeeds and calls `messages.create` with the expected `to`/`from_`/
      `body`; assert the call happens off the event loop (via
      `anyio.to_thread.run_sync`) so a slow mocked call doesn't block a
      concurrent request in the same test.
- [x] 9.2b Request OTP over `sms` with Twilio settings unset falls back to
      `UnconfiguredSmsSender` and returns 503, not a false success.
- [x] 9.2c Request OTP over `whatsapp` always returns 503 (no real
      WhatsApp sender exists in this change).
- [x] 9.2d A mocked Twilio client raising `TwilioRestException` maps to a
      503 whose response body contains no Twilio error code/message, and
      is NOT cached under the request's `Idempotency-Key` — a retry with
      the same key re-attempts dispatch (design.md's Idempotency-Key
      refinement). Paired with a test proving the WhatsApp/unconfigured-SMS
      503 IS cached, to make the contrast observable rather than assumed.
- [x] 9.3 Channel/identifier mismatch is rejected with a validation error.
- [x] 9.4 Expired code is rejected (advance time or set a near-zero TTL for
      the test).
- [x] 9.5 Wrong code decrements attempts; after `otp_max_attempts`
      consecutive failures the code is invalidated, including for the
      originally-correct code.
- [x] 9.6 A verified code cannot be reused for a second verification.
- [x] 9.7 Requesting a second OTP for the same identifier invalidates the
      first.
- [x] 9.8 Per-identifier rate limit returns 429 once exceeded (service-level
      and one endpoint-level test). The per-IP `slowapi` limiter is
      globally disabled under `ENVIRONMENT=test` (`core/rate_limit.py`),
      the same way every other feature's tests never exercise that layer —
      not a gap specific to this feature.
- [x] 9.9 Retried request/verify with the same `Idempotency-Key` returns
      the cached original response without re-dispatching or re-counting
      an attempt.
- [x] 9.10 No response body, and no captured log line, contains a
      plaintext code; log lines carry a masked identifier, not the full
      one (the response body legitimately echoes the caller's own
      identifier back to them, which is not a leak — see the spec's
      requirement text, which scopes masking to log lines specifically).

## 10. Documentation

- [x] 10.1 Add `docs/features/identity_verification.md` describing the two
      endpoints, the channel/sender model (real email, real SMS via
      Twilio, unconfigured WhatsApp), required Twilio settings, the
      Twilio trial-account restriction (can only send to pre-verified
      numbers until the account is upgraded — design.md's Risks), and the
      deferred integration into `invitations`/`registrations` (per
      `project-rules.md`'s "New Features" doc requirement).
- [x] 10.2 Update `docs/features/registrations.md`'s "Not yet built" /"No
      OTP verification" note to point at this feature instead of "no OTP
      mechanism exists anywhere in this codebase yet."
