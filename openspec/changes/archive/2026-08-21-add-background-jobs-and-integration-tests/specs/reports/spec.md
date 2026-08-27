## ADDED Requirements

### Requirement: Scheduled Rollup Snapshot Emailed to Tenant Admins
The system SHALL run a recurring background job that, once per day and for
every active tenant, computes the same cross-branch rollup the on-demand
endpoint reports and emails a summary of it to every user holding the Admin
role in that tenant. This is in addition to, not a replacement for, the
existing on-demand `GET /reports/branches/rollup` endpoint.

#### Scenario: Daily snapshot reaches every tenant admin and no one else
- **WHEN** the scheduled snapshot job runs for a tenant
- **THEN** every user holding the Admin role in that tenant receives the
  summary email, and no user without the Admin role receives it

#### Scenario: One tenant's snapshot failing does not block another tenant's
- **WHEN** the scheduled snapshot job fails while processing one tenant
  (e.g. an email-send error)
- **THEN** it still computes and sends the snapshot for every other active
  tenant in that same scheduled run

#### Scenario: Snapshot content matches the on-demand rollup
- **WHEN** the scheduled snapshot job computes a tenant's rollup
- **THEN** the branch-level and tenant-wide totals it reports match what
  `GET /reports/branches/rollup` would return for that tenant at the same
  point in time

#### Scenario: A redelivered snapshot task does not double-send the email
- **WHEN** the scheduled snapshot task for a tenant is redelivered and
  re-executed for the same scheduled run
- **THEN** the tenant's admins do not receive a duplicate summary email for
  that run
