# reports Specification

## Purpose

Baseline requirements for the `reports` capability — read-only, cross-branch
structural aggregation for admins (API-07's reporting half). Owns no table
of its own; reads across `org_structure` and `auth`'s tenant-scoped tables.

## Requirements

### Requirement: Cross-Branch Structural Rollup
The system SHALL provide a company-wide, read-only endpoint that reports,
for every branch in the tenant, its building/floor/department/reception-desk/
security-gate counts and active-employee headcount, plus tenant-wide totals
across all branches.

#### Scenario: Rollup includes every branch, including empty ones
- **WHEN** the rollup is requested for a tenant with branches that have no
  buildings/floors/departments/desks/gates/active employees at all
- **THEN** that branch still appears in the response with zero counts,
  rather than being omitted

#### Scenario: Rollup is company-wide, not branch-scoped
- **WHEN** the rollup endpoint is called
- **THEN** it requires only a company-wide permission (`reports:view`),
  never an `X-Branch-ID` header — the endpoint's purpose is comparing
  across every branch in one response

#### Scenario: Aggregation uses grouped queries, not a per-branch loop
- **WHEN** the rollup is computed for a tenant with multiple branches
- **THEN** each count type (buildings, floors, departments, desks, gates,
  active employees) is produced by one grouped-by-branch query, not one
  query per branch

#### Scenario: Tenant-wide totals sum correctly across branches
- **WHEN** the rollup is computed
- **THEN** each tenant-wide total equals the sum of that count across every
  branch in the response

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
