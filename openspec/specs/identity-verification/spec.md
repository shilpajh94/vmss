# Identity Verification Specification

## Purpose

Lets an unauthenticated visitor prove they control an email address or phone
number, by requesting and then submitting a one-time code, before that
contact is trusted anywhere downstream in the visitor-facing registration
flow.

## Requirements

### Requirement: A visitor can request an OTP for an identifier over a chosen channel
The system SHALL accept an unauthenticated request naming an identifier (an
email address or a phone number) and a delivery channel (`email`, `sms`, or
`whatsapp`), and SHALL send a numeric one-time code to that identifier over
the requested channel. An `email` channel SHALL require the identifier to be
a valid email address; `sms`/`whatsapp` channels SHALL require the
identifier to be a valid phone number. A mismatch between channel and
identifier format SHALL be rejected with a validation error before any code
is generated or sent.

#### Scenario: Request an OTP over email
- **WHEN** a visitor requests an OTP for a valid email identifier with
  channel `email`
- **THEN** the system generates a one-time code, dispatches it to that email
  address, and returns a success response with no code value in the body

#### Scenario: Request an OTP over SMS or WhatsApp
- **WHEN** a visitor requests an OTP for a valid phone identifier with
  channel `sms` or `whatsapp`
- **THEN** the system generates a one-time code and dispatches it over the
  requested channel

#### Scenario: Identifier does not match the requested channel
- **WHEN** a visitor requests an OTP with channel `email` but a phone-shaped
  identifier, or channel `sms`/`whatsapp` but an email-shaped identifier
- **THEN** the request is rejected with a validation error and no code is
  generated

### Requirement: OTP codes are short-lived and single-use
Each generated code SHALL expire 5 minutes after issuance and SHALL be
usable for at most one successful verification. Requesting a new OTP for the
same identifier before the previous code expires SHALL invalidate the
previous code, so at most one code is valid for a given identifier at a
time.

#### Scenario: Expired code is rejected
- **WHEN** a visitor submits a code more than 5 minutes after it was issued
- **THEN** verification fails and the system reports the code as expired,
  without indicating whether the code itself was otherwise correct

#### Scenario: A previously verified code cannot be reused
- **WHEN** a visitor submits a code that has already been successfully
  verified once
- **THEN** verification fails as if the code did not exist

#### Scenario: Requesting a new code supersedes the previous one
- **WHEN** a visitor requests a second OTP for the same identifier before
  the first has expired or been verified
- **THEN** the first code is no longer accepted and only the newly issued
  code can succeed

### Requirement: Verifying a correct code issues a short-lived verified-contact proof
The system SHALL accept an unauthenticated verification request naming the
identifier and the submitted code. WHEN the code matches the current
unexpired, unused code for that identifier, the system SHALL mark the
identifier as verified for that request and SHALL return a signed,
short-lived proof that a later caller can present to demonstrate this
identifier was verified. The proof SHALL be scoped to the specific
identifier and SHALL NOT grant any authenticated-user privilege.

#### Scenario: Correct, unexpired code verifies successfully
- **WHEN** a visitor submits the correct, still-valid code for an identifier
- **THEN** the system returns a success response containing a verified-
  contact proof tied to that identifier

#### Scenario: Incorrect code fails verification
- **WHEN** a visitor submits a code that does not match the current code
  issued for that identifier
- **THEN** verification fails and no proof is returned

### Requirement: Failed verification attempts are capped per code
The system SHALL track failed verification attempts per issued code and
SHALL invalidate the code after 5 consecutive failed attempts, requiring the
visitor to request a new OTP. The response for a failed attempt SHALL NOT
reveal the correct code or the remaining attempt count beyond a generic
failure indication.

#### Scenario: Code is invalidated after too many failed attempts
- **WHEN** a visitor submits 5 consecutive incorrect codes for the same
  issued code
- **THEN** that code is invalidated and a subsequent submission of the
  originally correct code also fails, requiring a new OTP request

### Requirement: OTP requests and verification attempts are rate-limited
As public, unauthenticated write endpoints, both requesting and verifying an
OTP SHALL be rate-limited per the posture `security-architecture.md` §2
requires for visitor-facing public endpoints, keyed by client IP and by the
target identifier, to resist SMS/WhatsApp-bombing and brute-force guessing.

#### Scenario: Requests within the limit succeed
- **WHEN** a caller stays under the configured rate limit for OTP requests
  or verification attempts
- **THEN** each request is processed normally

#### Scenario: Requests over the limit are rejected
- **WHEN** a caller exceeds the configured rate limit for either endpoint
- **THEN** the system rejects further requests with 429 until the window
  resets

### Requirement: OTP delivery over an unconfigured channel fails loudly
WHEN a request names a delivery channel (`sms` or `whatsapp`) for which no
gateway is configured, the system SHALL reject the request with a clear
service-unavailable error rather than reporting success without having sent
anything.

#### Scenario: Requesting OTP over an unconfigured channel
- **WHEN** a visitor requests an OTP over a channel whose gateway is not
  configured in the current deployment
- **THEN** the system returns a service-unavailable error and does not
  report the OTP as sent

### Requirement: OTP request and verification support retried requests without duplication
Both the request and the verify endpoint SHALL accept an `Idempotency-Key`
header (`api-conventions.md` §3). A retried request carrying the same key
SHALL return the original response instead of re-executing — re-sending a
code (which would burn a second SMS/WhatsApp/email send) or re-counting a
verification attempt against the failed-attempt cap.

#### Scenario: Retried OTP request with the same idempotency key
- **WHEN** a caller retries an OTP request with the same `Idempotency-Key`
  as an earlier successful request
- **THEN** the system returns the original response and does not dispatch a
  second code

#### Scenario: Retried verification with the same idempotency key
- **WHEN** a caller retries a verification request with the same
  `Idempotency-Key` as an earlier attempt
- **THEN** the system returns the original response and does not count a
  second attempt against the failed-attempt cap

### Requirement: OTP codes and full identifiers are never exposed in plaintext outside delivery
Generated codes SHALL never appear in any API response, log line, or error
message. Log lines for OTP requests and verification attempts SHALL
reference the identifier in masked form only (per
`logging-observability.md` §2's "never log OTP in plaintext" rule).

#### Scenario: OTP request response contains no code
- **WHEN** an OTP request succeeds
- **THEN** the response body and all log lines for that request contain no
  plaintext code and no unmasked identifier

#### Scenario: Verification failure response contains no code
- **WHEN** a verification attempt fails for any reason
- **THEN** the response body reveals neither the correct code nor which
  part of the submission was wrong beyond "invalid or expired code"
