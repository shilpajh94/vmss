## ADDED Requirements

### Requirement: A Scheduled Snapshot Email Dispatch Failure Is Logged With Enough Detail To Diagnose
WHEN the configured SMTP gateway rejects or fails to send a scheduled
rollup-snapshot summary email to a tenant's admins, the system SHALL log
the configured SMTP host and port and the underlying exception's type and
message, in addition to the tenant context already logged for that
failure. This SHALL NOT change the existing per-tenant isolation behavior
— one tenant's dispatch failure still does not block the snapshot job from
running for any other tenant — and the log line SHALL NOT include any
recipient's email address or SMTP credential value.

#### Scenario: A snapshot email dispatch failure logs host, port, and exception detail
- **WHEN** the configured SMTP gateway rejects or fails to send a tenant's
  scheduled rollup-snapshot summary email
- **THEN** the log line for that failure includes the configured SMTP host
  and port and the underlying exception's type and message

#### Scenario: Dispatch-failure logging never includes the recipient identifier or credentials
- **WHEN** a scheduled snapshot email dispatch failure is logged
- **THEN** the log line contains no recipient email address or SMTP
  credential value
