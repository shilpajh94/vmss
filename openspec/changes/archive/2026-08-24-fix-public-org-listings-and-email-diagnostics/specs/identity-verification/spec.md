## ADDED Requirements

### Requirement: A configured channel's dispatch failure is logged with enough detail to diagnose
WHEN a configured delivery gateway (SMTP for `email`, Twilio for `sms`/
`whatsapp`) rejects or fails to send an OTP, the system SHALL log the
target channel, the gateway's connection detail relevant to that channel
(for email: the configured SMTP host and port), and the underlying
exception's type and message, in addition to the masked identifier already
logged. This SHALL NOT change the client-facing response: the caller still
receives a generic service-unavailable error with no gateway detail, and no
OTP code or unmasked identifier SHALL ever appear in the log line, per the
existing "OTP codes and full identifiers are never exposed in plaintext"
requirement.

#### Scenario: An email dispatch failure logs host, port, and exception detail
- **WHEN** the configured SMTP gateway rejects or fails to send an OTP email
- **THEN** the log line for that failure includes the configured SMTP host
  and port and the underlying exception's type and message, alongside the
  already-masked identifier

#### Scenario: Dispatch-failure logging never includes credentials or the code
- **WHEN** any configured channel's dispatch failure is logged
- **THEN** the log line contains no SMTP/gateway credential value and no
  OTP code, regardless of how much detail is captured about the failure

#### Scenario: The client-facing error is unchanged by the added logging detail
- **WHEN** a configured channel's dispatch fails, before and after this
  logging change
- **THEN** the caller receives the same generic service-unavailable error
  and status code either way — the added detail is server-side only
