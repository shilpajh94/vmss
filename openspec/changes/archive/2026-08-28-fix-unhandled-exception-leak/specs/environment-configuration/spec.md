## ADDED Requirements

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
