## ADDED Requirements

### Requirement: Every Unauthenticated Endpoint Is Rate-Limited
Every endpoint that can be called without a bearer token SHALL carry a
per-client-IP rate limit, including the form-builder effective-config read,
the signed local-file download route and the email-asset route. An endpoint
added later without a limit SHALL fail an automated test that inventories
the unauthenticated routes.

#### Scenario: Effective form config is limited
- **WHEN** one client IP sends more requests per minute to
  `GET /form-builder/effective` than its configured limit
- **THEN** at least one of those requests receives a 429 in the standard
  error envelope

#### Scenario: Route inventory catches an unlimited public route
- **WHEN** the test suite runs and an unauthenticated route has no rate
  limit applied
- **THEN** the route-inventory test fails and names that route

### Requirement: Rate Limits Key on the Real Client Address Behind a Trusted Proxy
When the API runs behind a load balancer or reverse proxy listed in the
trusted-proxy setting, rate limits SHALL key on the client address that
proxy forwards, not the proxy's own address. Forwarded headers from an
untrusted peer SHALL be ignored.

#### Scenario: Two clients behind one proxy have separate buckets
- **WHEN** two different clients reach the API through the same trusted
  proxy, and one exhausts its limit on `POST /auth/login`
- **THEN** the other client's next login request is not rejected with 429

#### Scenario: Spoofed forwarded header from an untrusted peer
- **WHEN** a client that is not a trusted proxy sends a forged
  `X-Forwarded-For` header
- **THEN** its requests are rate-limited on its own connection address
