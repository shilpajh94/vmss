## MODIFIED Requirements

### Requirement: Public Authentication Endpoints Are Rate-Limited Per IP
Every unauthenticated login endpoint SHALL be rate-limited per client IP,
and SHALL reject a request that exceeds its limit with 429, before any
credential verification is attempted.

#### Scenario: Tenant-user login is rate-limited
- **WHEN** more than 3 requests per minute from the same IP are sent to
  `POST /auth/login`
- **THEN** at least one of those requests receives a 429 response

#### Scenario: Superadmin login is rate-limited
- **WHEN** more than 5 requests per minute from the same IP are sent to
  `POST /platform/auth/login`
- **THEN** at least one of those requests receives a 429 response
