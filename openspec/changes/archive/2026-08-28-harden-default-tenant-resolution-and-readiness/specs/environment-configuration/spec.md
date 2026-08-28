## ADDED Requirements

### Requirement: Readiness Reporting Verifies the Configured Default Tenant and Branch Resolve
Several public, unauthenticated endpoints (walk-in registration without a
device credential, identity verification, invitation tracking) resolve a
single server-configured default tenant, and in one case a default branch
within it, rather than a caller-supplied identifier. The readiness probe
SHALL verify that this configured default tenant — and, separately, the
configured default walk-in branch — resolves to an active row, in addition
to verifying database and cache connectivity, so a deployment where these
settings do not resolve is reported unready instead of healthy.

#### Scenario: Readiness passes when the default tenant and branch are correctly provisioned
- **WHEN** the readiness endpoint is called, the database and cache are
  reachable, and the configured default tenant slug resolves to an active
  tenant whose schema contains an active branch matching the configured
  default branch code
- **THEN** the readiness endpoint reports ready

#### Scenario: Readiness fails when the configured default tenant does not resolve
- **WHEN** the readiness endpoint is called and the configured default
  tenant slug does not match any tenant, or matches one that is inactive
- **THEN** the readiness endpoint reports not-ready and the response
  distinguishes this cause from a database/cache connectivity failure

#### Scenario: Readiness fails when the configured default branch does not resolve
- **WHEN** the readiness endpoint is called, the configured default tenant
  resolves and is active, but the configured default walk-in branch code
  does not match any branch in that tenant's schema, or matches one that is
  inactive
- **THEN** the readiness endpoint reports not-ready and the response
  distinguishes this cause from a default-tenant resolution failure
