## ADDED Requirements

### Requirement: The Rollup Snapshot Email Uses the Branded Snapshot Template
The scheduled rollup snapshot email SHALL be rendered from the branded
daily-snapshot template (see the `email-notifications` capability), with a
plain-text part. It SHALL have the subject "Daily branch rollup —
{weekday, day month year}". It SHALL show the tenant-wide totals, then a
table with one row per branch carrying the same per-branch figures the
current plain-text summary carries. It SHALL greet each admin by display
name, or "Hello," when no trustworthy name exists. Which recipients get
it, when it is sent, and its one-send-per-day idempotency are unchanged.

#### Scenario: Snapshot email shows a per-branch table
- **WHEN** the snapshot job runs for a tenant with two branches
- **THEN** each admin receives an HTML email with the tenant totals and a
  two-row branch table whose figures match `GET /reports/branches/rollup`,
  plus a plain-text part listing the same figures

#### Scenario: Tenant with no branches
- **WHEN** the snapshot job runs for a tenant with zero branches
- **THEN** the email states that there are no branches to report instead of
  rendering an empty table
