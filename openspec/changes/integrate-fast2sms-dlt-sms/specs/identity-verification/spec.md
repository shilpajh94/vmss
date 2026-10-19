## MODIFIED Requirements

### Requirement: A configured channel's dispatch failure is logged with enough detail to diagnose
WHEN a configured delivery gateway (SMTP for `email`, Fast2SMS for `sms` and `whatsapp`) rejects or fails to send an OTP, the system SHALL log the
target channel, the gateway's connection detail relevant to that channel
(for email: the configured SMTP host and port; for SMS and WhatsApp: the HTTP status and Fast2SMS's response message), and the underlying
exception's type and message, in addition to the masked identifier already
logged. This SHALL NOT change the client-facing response: the caller still
receives a generic service-unavailable error with no gateway detail, and no
OTP code, API key or unmasked identifier SHALL ever appear in the log line, per the
existing "OTP codes and full identifiers are never exposed in plaintext"
requirement.

#### Scenario: An email dispatch failure logs host, port, and exception detail
- **WHEN** the configured SMTP gateway rejects or fails to send an OTP email
- **THEN** the log line for that failure includes the configured SMTP host
  and port and the underlying exception's type and message, alongside the
  already-masked identifier

#### Scenario: An SMS or WhatsApp dispatch failure logs status and gateway message
- **WHEN** Fast2SMS rejects or fails to send an OTP over `sms` or `whatsapp`
- **THEN** the log line includes the HTTP status and Fast2SMS's message alongside the masked identifier, with no API key and no code

#### Scenario: Dispatch-failure logging never includes credentials or the code
- **WHEN** any configured channel's dispatch failure is logged
- **THEN** the log line contains no SMTP/gateway credential value and no
  OTP code, regardless of how much detail is captured about the failure

#### Scenario: The client-facing error is unchanged by the added logging detail
- **WHEN** a configured channel's dispatch fails, before and after this
  logging change
- **THEN** the caller receives the same generic service-unavailable error

### Requirement: The Emailed Verification Code Uses the Branded Verification Template
WHEN an OTP is dispatched over the `email` channel, the email SHALL be
rendered from the branded verification-code template (see the
`email-notifications` capability), with a plain-text part. It SHALL have
the subject "Your verification code", a lead line explaining what the code
is for, the code in a highlighted monospace box, the code's lifetime in
minutes (from the configured OTP TTL) and that it is single use, and a
"Keep it private" note. That note SHALL say the code will never be asked
for by phone or message and that the email can be ignored if not
requested. The email SHALL contain no other identifier, tracking data or
link. SMS delivery SHALL use the DLT-approved OTP template (see the
`sms-notifications` capability) carrying the code and its lifetime in minutes as variables; WhatsApp
delivery SHALL use the approved WhatsApp authentication template (see the
`whatsapp-notifications` capability) carrying the code. The code SHALL still never appear in any log line, API response or
error message.

#### Scenario: Verification email renders the code in the branded template
- **WHEN** a visitor requests an OTP over email and the configured TTL is 300
  seconds
- **THEN** the delivered email has subject "Your verification code", an HTML
  part showing the code inside the dashed code box with "expires in 5
  minutes" and "can only be used once", a "Keep it private" note, and a
  plain-text part carrying the same code and expiry

#### Scenario: Rendering failure still delivers the code
- **WHEN** the verification template fails to render
- **THEN** the system logs the failure at `ERROR` without the code and sends
  the plain one-line text ("Your verification code is … It expires in N
  minutes.") so the visitor can still verify

#### Scenario: SMS delivery is unchanged
- **WHEN** a visitor requests an OTP over `sms` or `whatsapp`
- **THEN** the message is not the email template: `sms` is sent through the DLT-approved OTP template with the code and expiry minutes as variables, and `whatsapp` through the approved WhatsApp authentication template with the code

### Requirement: OTP delivery over WhatsApp works once configured
WHEN a visitor requests an OTP over `whatsapp` and the Fast2SMS WhatsApp settings are configured, the system SHALL deliver the code through the WhatsApp authentication template. WHEN they are not configured the existing "unconfigured channel fails loudly" requirement still applies.

#### Scenario: OTP over WhatsApp is delivered
- **WHEN** a visitor requests an OTP with channel `whatsapp` and a valid phone number, and WhatsApp is configured
- **THEN** one Fast2SMS WhatsApp template message carrying the code is sent and the request succeeds

#### Scenario: WhatsApp not configured
- **WHEN** WhatsApp settings are blank and a visitor requests an OTP over `whatsapp`
- **THEN** the system returns the service-unavailable error and nothing is sent
