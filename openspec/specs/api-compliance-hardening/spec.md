# api-compliance-hardening Specification

## Purpose

Captures reliability and contract-accuracy requirements surfaced by a
compliance audit of the 12 already-delivered core API items — deterministic
automated test outcomes, invitation-creation idempotency, and track-endpoint
response-contract accuracy — so these stop being implicit assumptions and
become verifiable, testable requirements in their own right.

## Requirements

### Requirement: Deterministic Test Suite Execution
The automated test suite for any tenant-scoped feature (`auth`, `org_structure`,
`platform`, `reports`, `invitations`, and any future tenant-scoped feature)
SHALL produce the same pass/fail outcome for a given set of tests regardless of
whether that feature's tests run alone or as part of the full suite, and
regardless of test execution order within the file. A mutation that triggers a
background write (an audit-log entry, a queued notification dispatch) during a
test SHALL NOT fail due to that background write operating against
different/stale data than the test's own request saw, and SHALL NOT leave
residual state that causes an unrelated, later test to fail.

#### Scenario: Feature test file passes in isolation
- **WHEN** a single feature's test file (e.g. `invitations/tests.py`) is run by
  itself, with no other test file executed before or after it in the same
  session
- **THEN** every test in that file passes, with the same outcome as when the
  full suite is run

#### Scenario: Mutating endpoint with a background audit write succeeds
- **WHEN** an authenticated request creates or modifies a tenant-scoped entity
  and the request handler queues a background audit-log write referencing the
  acting user
- **THEN** the background write succeeds and does not raise a foreign-key or
  stale-row error, even though the acting user was created earlier in the same
  test run rather than in a separate, already-committed transaction

#### Scenario: Full suite run is reliably green
- **WHEN** the complete `pytest` suite is run twice in a row against a freshly
  reset test database
- **THEN** both runs report an identical set of passing and failing tests (zero
  flaked tests) for every tenant-scoped feature

### Requirement: Invitation Creation Idempotency
An authenticated invitation-creation request SHALL accept an optional
`Idempotency-Key` header. When a request with a given key (scoped to the
caller's tenant) is retried before the cached window expires, the system SHALL
return the same response as the original request without creating a second
invitation.

#### Scenario: Retried invitation creation with the same idempotency key
- **WHEN** a caller holding `invitations:create` submits `POST /invitations`
  with an `Idempotency-Key` header, and then retries the identical request
  with the same header value and the same tenant context within the cache
  window
- **THEN** exactly one invitation is created, and both requests receive the
  same response body

#### Scenario: Same key reused after the cache window expires
- **WHEN** a caller retries a `POST /invitations` request with an
  `Idempotency-Key` value that was used more than the cache window ago
- **THEN** the system processes the request as a new invitation creation

#### Scenario: Invitation creation without an idempotency key
- **WHEN** a caller submits `POST /invitations` with no `Idempotency-Key`
  header
- **THEN** the request is processed normally, exactly as it is today

### Requirement: Track Endpoint Response Contract Accuracy
The invitation track-request endpoint's documented response contract SHALL
accurately describe every response shape it can actually return for its two
lookup modes (by tracking ID, and by primary contact email), so generated API
documentation and client code reflect real behavior rather than a shape the
endpoint never sends for one of its lookup modes.

#### Scenario: Lookup by tracking ID matches its documented shape
- **WHEN** a caller looks up an invitation by tracking ID
- **THEN** the response matches the full-detail shape declared for that lookup
  mode in the API's generated schema

#### Scenario: Lookup by email matches its documented shape
- **WHEN** a caller looks up invitations by the primary contact's email
- **THEN** the response matches the minimal-disclosure summary shape declared
  for that lookup mode in the API's generated schema, not the full-detail shape
  used by tracking-ID lookup
