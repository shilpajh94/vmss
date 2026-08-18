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
