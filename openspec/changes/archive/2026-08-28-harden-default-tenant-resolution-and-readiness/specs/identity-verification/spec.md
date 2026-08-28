## ADDED Requirements

### Requirement: Default-Tenant Misconfiguration Is Reported and Logged as a Server Error
OTP request and verification resolve a single server-configured default
tenant (there being no caller-supplied tenant identifier on these
unauthenticated endpoints). When that default tenant does not resolve —
because no tenant matches the configured slug, or the matching tenant is
inactive — this is a server-side configuration gap, not a property of the
caller's request, and SHALL be logged at `ERROR` distinguishing "no such
tenant" from "tenant inactive", consistent with the equivalent requirement
already defined for walk-in registration's default-tenant/branch fallback.

#### Scenario: Unconfigured default tenant is logged as a server misconfiguration
- **WHEN** an OTP request or verification call is made and the configured
  default tenant slug does not match any tenant, or matches one that is
  inactive
- **THEN** the rejection is logged at `ERROR`
- **AND** the log distinguishes whether no such tenant row exists at all
  versus the row exists but is inactive, so an operator can tell the fix
  from the log alone

#### Scenario: Client-facing response is unchanged
- **WHEN** the default tenant fails to resolve for an OTP request or
  verification call
- **THEN** the caller receives the same response shape and status code this
  endpoint already returns for that condition today — only the server-side
  log gains the `ERROR`-level detail
