## Purpose

Defines how the system delivers SMS to visitors through the Fast2SMS DLT route, so that OTPs and invitation lifecycle notifications reach visitors whose preferred contact method is SMS in compliance with Indian DLT template rules.

## ADDED Requirements

### Requirement: SMS is delivered through Fast2SMS using DLT templates
The system SHALL send every SMS through the Fast2SMS DLT route, supplying the configured sender ID, the DLT-approved template ID for that message type, the ordered template variable values separated by `|`, and the recipient number, authenticated with the configured API key. The system SHALL NOT send free-text SMS bodies.

#### Scenario: A templated SMS is sent
- **WHEN** an SMS is dispatched for a message type that has a configured template ID
- **THEN** one Fast2SMS DLT request is made with that template ID, the configured sender ID, the variable values in template order joined by `|`, and the recipient number

#### Scenario: A variable value contains the separator
- **WHEN** a variable value (e.g. a denial reason) contains `|`
- **THEN** the separator is removed or replaced before sending so the variable count still matches the template

#### Scenario: A message type has no template configured
- **WHEN** an SMS is requested for a message type whose template ID setting is blank
- **THEN** no request is made and the dispatch fails loudly as "not configured"

### Requirement: Recipient phone numbers are normalised for Fast2SMS
The system SHALL convert a stored phone number to the form Fast2SMS expects (a 10-digit Indian mobile number) before sending, accepting common stored forms such as `+91XXXXXXXXXX`, `91XXXXXXXXXX` and `0XXXXXXXXXX`.

#### Scenario: Country-code prefixed number
- **WHEN** the recipient number is `+919876543210`
- **THEN** the request's `numbers` value is `9876543210`

#### Scenario: Number that cannot be normalised
- **WHEN** the recipient number is not a valid Indian mobile number after normalisation
- **THEN** no request is made and the dispatch fails as a non-retryable error

### Requirement: Unconfigured SMS fails loudly
When the Fast2SMS API key or sender ID is not configured, SMS dispatch SHALL fail with a clear not-configured error rather than reporting success.

#### Scenario: Missing API key
- **WHEN** an SMS is dispatched and the API key is blank
- **THEN** the dispatch raises the not-configured error and nothing is sent

### Requirement: Fast2SMS failures are reported without leaking detail
The system SHALL treat a non-200 response, a response with `return: false`, or a network error as a dispatch failure. It SHALL log channel, masked recipient, HTTP status and Fast2SMS's message at `WARNING`, and SHALL NOT log the API key, OTP codes or unmasked numbers. Client-facing responses SHALL stay generic.

#### Scenario: Fast2SMS rejects the request
- **WHEN** Fast2SMS returns `return: false`
- **THEN** a dispatch error is raised, the log line has the masked number and Fast2SMS's message but no API key or code, and the caller sees only a generic service-unavailable error (OTP) or the task is retried per background-job rules (invitations)

#### Scenario: Network failure on an invitation SMS
- **WHEN** the Fast2SMS request times out inside a Celery notification task
- **THEN** the task retries with backoff and logs at `ERROR` with tenant and invitation id once retries are exhausted

### Requirement: Visitors with SMS preference receive invitation notifications by SMS
For every invitation lifecycle notification that is emailed when `preferredContactMethod` is `email`, the system SHALL instead send a templated SMS to the primary contact's phone when `preferredContactMethod` is `sms`, and SHALL NOT send both. Covered events: registration pending approval, registration confirmed (with tracking ID), registration denied (with reason), visit rescheduled (new date and time), and visit details changed.

#### Scenario: Confirmation by SMS
- **WHEN** an invitation is approved and its primary contact prefers `sms`
- **THEN** an SMS using the confirmation template is sent with the tracking ID, and no email is sent

#### Scenario: Reschedule by SMS
- **WHEN** a visit is rescheduled and the contact prefers `sms`
- **THEN** an SMS using the reschedule template is sent with the new date, new time and tracking ID

#### Scenario: Email preference unchanged
- **WHEN** the contact prefers `email`
- **THEN** the email is sent as before and no SMS is sent

### Requirement: SMS gateway settings are environment-driven
The Fast2SMS API key, sender ID and per-message-type template IDs SHALL be read from environment settings and documented in `.env.example`, with secrets blank rather than placeholder-filled.

#### Scenario: New setting documented
- **WHEN** a Fast2SMS setting exists in application config
- **THEN** a matching entry exists in `.env.example`
