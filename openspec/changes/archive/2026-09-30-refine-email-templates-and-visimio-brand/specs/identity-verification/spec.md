## ADDED Requirements

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
link. SMS and WhatsApp delivery SHALL keep their existing short one-line
text. The code SHALL still never appear in any log line, API response or
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
- **THEN** the message body is the existing one-line text, not the email
  template
