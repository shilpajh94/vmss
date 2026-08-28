# environment-configuration Specification

## Purpose

Defines how every runtime setting the API depends on (database, cache/broker,
auth secrets, mail, SMS, file storage, CORS, tenancy, logging) is sourced from
environment variables, so no environment-specific value — least of all a
database or cache credential — ships as a real-looking default baked into
source code.

## Requirements

### Requirement: No Hardcoded Connection Credentials
The system SHALL NOT define a default value for any database, cache, or
message-broker connection setting (host, port, username, password, or a full
connection string) that resolves to a real, usable connection target. Every
such value SHALL be required from the environment, with no fallback other
than a value that is obviously non-functional (e.g. empty) or explicitly
documented as local-development-only in a non-committed file.

#### Scenario: Application refuses to start with no environment configured
- **WHEN** the application is started with no `.env` file present and no
  database-related environment variables set in the process environment
- **THEN** startup fails with a configuration error naming the missing
  setting, rather than silently connecting to a hardcoded host

#### Scenario: Committed example file contains no real credential
- **WHEN** `.env.example` is inspected
- **THEN** every database, cache, and broker value is a placeholder or
  documented as a local-dev-only convenience value, not a credential valid
  against any shared or production system

### Requirement: Database Connection Is Configured By Component Variables
The system SHALL accept the database connection as a set of discrete
environment variables — connection driver, host, port, database name,
username, and password — and SHALL assemble the connection string used to
reach the database from those parts. If a single full database connection
URL is instead present in the environment, the system SHALL use that value
as-is in preference to assembling one from the component variables.

#### Scenario: Component variables produce a working connection
- **WHEN** the connection driver, host, port, database name, username, and
  password are set individually in the environment, and no full connection
  URL is set
- **THEN** the application connects to the database at the specified
  host/port/database using the specified credentials

#### Scenario: A full connection URL overrides component variables
- **WHEN** a full database connection URL is set in the environment
  alongside (or instead of) the component variables
- **THEN** the application connects using the full URL, ignoring any
  component variables also present

### Requirement: Cache and Broker Connections Are Configured By Component Variables
The system SHALL accept the cache/message-broker connection as discrete
host, port, and password environment variables plus a distinct logical
database index per purpose (application cache, task queue broker, task
result backend), and SHALL assemble each purpose's connection target from
those parts. If a full connection URL is instead present for a given
purpose, the system SHALL use that value as-is.

#### Scenario: Distinct logical databases stay isolated
- **WHEN** the cache, task-queue-broker, and task-result-backend logical
  database indices are configured to different values on the same
  host/port
- **THEN** data written for one purpose (e.g. cached lookups) is not visible
  through another purpose's connection (e.g. the task broker)

### Requirement: Every Setting Is Documented in the Example File
The committed environment example file SHALL declare every environment
variable the application reads, grouped by the service or concern it
configures, with each entry either a safe placeholder or a comment
explaining what a real deployment must supply.

#### Scenario: New setting added without a corresponding example entry is a defect
- **WHEN** a new environment-backed setting is added to the application's
  configuration
- **THEN** the example file is updated in the same change to declare that
  setting, so no setting exists that a deployer cannot discover from the
  example file alone

### Requirement: Log Verbosity Is Configurable Without a Code Change
The system SHALL read the minimum log level to emit from an environment
variable, defaulting to a production-safe level, so verbosity can be raised
for diagnosis in a given environment without modifying and redeploying code.

#### Scenario: Debug logging enabled via environment only
- **WHEN** the log-level environment variable is set to a more verbose level
  than the default in a given environment
- **THEN** log lines at that verbosity appear in that environment's output
  without any source code change

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

### Requirement: Debug Mode Cannot Be Enabled Outside Local/Testing Environments
The system SHALL only run with framework debug mode enabled when the
configured environment is `local` or `testing`. If the debug-mode
environment variable is set to enable it while the configured environment
is anything else (e.g. `staging`, `production`), the system SHALL run with
debug mode disabled rather than honoring the variable, so a deployment that
fails to explicitly disable debug mode is not exposed to debug-mode
behavior (including verbose error responses) as a result.

#### Scenario: Debug variable ignored in production
- **WHEN** the environment is configured as `production` and the debug-mode
  environment variable is set to enable debug mode
- **THEN** the system runs with debug mode disabled

#### Scenario: Debug variable ignored in staging
- **WHEN** the environment is configured as `staging` and the debug-mode
  environment variable is set to enable debug mode
- **THEN** the system runs with debug mode disabled

#### Scenario: Debug variable honored in local and testing
- **WHEN** the environment is configured as `local` or as `testing` and the
  debug-mode environment variable is set to enable debug mode
- **THEN** the system runs with debug mode enabled

### Requirement: Unhandled Exceptions Never Expose Internal Details to Clients When Debug Mode Is Disabled
Whenever debug mode is disabled, regardless of where in the request-handling
path an exception is raised — including inside request-scoped middleware
that runs before routing, not only inside a route handler — the system
SHALL return the standard error response envelope with a generic message
and a `500` status code, and SHALL NOT return a stack trace, file path,
source line, or any other framework-internal diagnostic detail in the
response body. Combined with the previous requirement, this guarantees no
`staging`/`production` deployment can expose these details regardless of
where an exception originates, since debug mode can never be enabled there.
A framework debug traceback remains an accepted, intentional result only
when debug mode is enabled (`local`/`testing` only) — that is debug mode's
purpose in local development, not a leak.

#### Scenario: Exception raised inside a route handler with debug disabled
- **WHEN** debug mode is disabled and a request causes an unhandled
  exception inside a route's service or repository call
- **THEN** the client receives the standard error response envelope with a
  generic message and status `500`, with no stack trace or internal detail
  in the body

#### Scenario: Exception raised inside request-scoped middleware with debug disabled
- **WHEN** debug mode is disabled and a request causes an unhandled
  exception inside middleware that runs before the route handler (e.g.
  request-id binding)
- **THEN** the client receives the same standard error response envelope,
  with no stack trace or internal detail in the body, exactly as it would
  if the exception had been raised inside the route handler itself
