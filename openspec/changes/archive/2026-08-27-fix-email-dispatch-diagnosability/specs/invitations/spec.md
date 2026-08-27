## ADDED Requirements

### Requirement: A Confirmation or Approval Email Dispatch Failure Is Logged With Enough Detail To Diagnose
WHEN the configured SMTP gateway rejects or fails to send a visit-
confirmation, tracking-only, or approval notification email, the system
SHALL log the configured SMTP host and port and the underlying exception's
type and message, in addition to the tenant and invitation context already
logged on retry exhaustion. This SHALL NOT change the client-facing
response — invitation creation and approval continue to respond
successfully regardless of dispatch outcome (dispatch is asynchronous) —
and the log line SHALL NOT include the recipient's email address, phone
number, or any OTP/credential value.

#### Scenario: An email dispatch failure logs host, port, and exception detail
- **WHEN** the configured SMTP gateway rejects or fails to send a
  confirmation, tracking-only, or approval notification email
- **THEN** the log line for that failure includes the configured SMTP host
  and port and the underlying exception's type and message

#### Scenario: Dispatch-failure logging never includes the recipient identifier or credentials
- **WHEN** an email dispatch failure is logged
- **THEN** the log line contains no recipient email address, phone number,
  or SMTP credential value

#### Scenario: Retry and exhaustion behavior is unchanged by the added logging
- **WHEN** an email dispatch fails, before and after this logging change
- **THEN** the task retries with the same backoff and maximum-retry policy,
  and the response returned to the caller that created or approved the
  invitation is unaffected
