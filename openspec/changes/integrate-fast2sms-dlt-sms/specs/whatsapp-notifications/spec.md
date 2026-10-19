## Purpose

Defines how the system delivers WhatsApp messages to visitors through the Fast2SMS WhatsApp API, so OTPs and invitation lifecycle notifications reach visitors whose preferred contact method is WhatsApp.

## ADDED Requirements

### Requirement: WhatsApp is delivered through Fast2SMS using approved templates
The system SHALL send every WhatsApp message as a template message via `POST https://www.fast2sms.com/dev/whatsapp/{version}/{phone_number_id}/messages` with an `Authorization` API-key header, supplying the configured template name for that message type, the configured language code, the ordered body variable values as `text` parameters, and the recipient number. The system SHALL NOT send free-text WhatsApp messages.

#### Scenario: A templated WhatsApp message is sent
- **WHEN** a WhatsApp message is dispatched for a message type that has a configured template name
- **THEN** one Fast2SMS WhatsApp request is made with that template name, the language code, a `body` component whose parameters are the variables in template order, and the normalised recipient

#### Scenario: OTP uses the authentication template
- **WHEN** an OTP is sent over WhatsApp
- **THEN** the request carries the code both as the body parameter and as the `url` button parameter at index `0`, as the authentication template requires

#### Scenario: A message type has no template configured
- **WHEN** a WhatsApp message is requested for a type whose template name is blank
- **THEN** no request is made and the dispatch fails loudly as "not configured"

### Requirement: Recipient numbers are normalised for WhatsApp
The system SHALL convert a stored phone number to the country-code form WhatsApp expects (`91` followed by a 10-digit Indian mobile number), accepting `+91XXXXXXXXXX`, `91XXXXXXXXXX`, `0XXXXXXXXXX` and bare 10-digit forms, using the same validation as SMS.

#### Scenario: Country-code prefixed number
- **WHEN** the recipient number is `+919876543210`
- **THEN** the request's `to` value is `919876543210`

#### Scenario: Invalid number
- **WHEN** the number is not a valid Indian mobile number after normalisation
- **THEN** no request is made and the dispatch fails as a non-retryable error

### Requirement: Unconfigured WhatsApp fails loudly
When the Fast2SMS API key, WhatsApp phone number ID or the message type's template name is blank, WhatsApp dispatch SHALL fail with a clear not-configured error rather than reporting success.

#### Scenario: Missing phone number ID
- **WHEN** a WhatsApp message is dispatched and the phone number ID is blank
- **THEN** the not-configured error is raised and nothing is sent

### Requirement: WhatsApp failures are reported without leaking detail
The system SHALL treat a non-200 response, a response without a message id, or a network error as a dispatch failure. It SHALL log channel, masked recipient, HTTP status and the gateway's message at `WARNING`, and SHALL NOT log the API key, OTP codes or unmasked numbers. Client-facing responses SHALL stay generic.

#### Scenario: Fast2SMS rejects the WhatsApp request
- **WHEN** the response is non-200 or has no `messages[0].id`
- **THEN** a dispatch error is raised, the log has the masked number and gateway message but no key or code, and the OTP caller sees only a generic service-unavailable error

#### Scenario: Timeout in a notification task
- **WHEN** the request times out inside a Celery notification task
- **THEN** the task retries with backoff and logs at `ERROR` with tenant and invitation id once retries are exhausted

### Requirement: Visitors with WhatsApp preference receive invitation notifications by WhatsApp
For every invitation lifecycle notification that is emailed for `email` or texted for `sms`, the system SHALL instead send a templated WhatsApp message to the primary contact's phone when `preferredContactMethod` is `whatsapp`, and SHALL NOT also send email or SMS. Covered events: registration pending approval, confirmed (tracking ID), denied (reason), rescheduled (new date and time), and details changed.

#### Scenario: Confirmation by WhatsApp
- **WHEN** an invitation is approved and its primary contact prefers `whatsapp`
- **THEN** a WhatsApp template message with the tracking ID is sent, and no email or SMS is sent

#### Scenario: Reschedule by WhatsApp
- **WHEN** a visit is rescheduled and the contact prefers `whatsapp`
- **THEN** a WhatsApp message is sent with the new date, time and tracking ID

#### Scenario: Other preferences unchanged
- **WHEN** the contact prefers `email` or `sms`
- **THEN** no WhatsApp message is sent

### Requirement: WhatsApp gateway settings are environment-driven
The WhatsApp phone number ID, API version, language code and per-message-type template names SHALL be read from environment settings (the API key is shared with SMS) and documented in `.env.example`, with secrets blank.

#### Scenario: New setting documented
- **WHEN** a WhatsApp setting exists in application config
- **THEN** a matching entry exists in `.env.example`
