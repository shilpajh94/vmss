# rate-limiting Specification

## Purpose

Baseline requirements for the `rate-limiting` capability — the
`slowapi`-backed middleware protecting unauthenticated and
resource-expensive endpoints from brute-force/abuse and accidental
resource exhaustion (API-08's rate-limiting third,
`security-architecture.md` §2).

## Requirements

### Requirement: Public Authentication Endpoints Are Rate-Limited Per IP
Every unauthenticated login endpoint SHALL be rate-limited per client IP,
and SHALL reject a request that exceeds its limit with 429, before any
credential verification is attempted.

#### Scenario: Tenant-user login is rate-limited
- **WHEN** more than 5 requests per minute from the same IP are sent to
  `POST /auth/login`
- **THEN** at least one of those requests receives a 429 response

#### Scenario: Superadmin login is rate-limited
- **WHEN** more than 5 requests per minute from the same IP are sent to
  `POST /platform/auth/login`
- **THEN** at least one of those requests receives a 429 response

### Requirement: Resource-Expensive Authenticated Endpoints Are Also Rate-Limited
An authenticated endpoint whose cost per request is high enough to be a
resource-exhaustion risk on its own (independent of brute-force concerns)
SHALL still be rate-limited per client IP, as defense-in-depth alongside its
permission check.

#### Scenario: Tenant provisioning is rate-limited even though authenticated
- **WHEN** more than 3 requests per minute from the same IP are sent to
  `POST /platform/tenants` by an authenticated superadmin
- **THEN** at least one of those requests receives a 429 response

### Requirement: A Tripped Rate Limit Returns the Standard Error Envelope
A request rejected for exceeding its rate limit SHALL receive the same
`{success, message, errors}` response envelope every other error uses, not
a raw framework-default body.

#### Scenario: 429 response matches the standard envelope shape
- **WHEN** a rate limit trips on any protected endpoint
- **THEN** the 429 response body has `success: false` and a human-readable
  `message`, consistent with every other error response in the API
