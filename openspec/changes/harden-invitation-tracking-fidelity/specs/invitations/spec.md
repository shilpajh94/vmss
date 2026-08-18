## Purpose

Baseline requirements for the `invitations` capability — employee-created
pre-registration invitations (API-09) and the invited visitor's own
multi-step public self-registration (API-10) — including the tracking
lookup's field-completeness fix a compliance re-audit against a concrete
JSON payload contract surfaced.

## ADDED Requirements

### Requirement: Employee Creates a Single or Group Invitation Shell
The system SHALL let an authenticated, branch-scoped employee create an
invitation with a `registrationType` (`individual` or `group`) and a
minimal primary contact, generating a human-readable expiry-bound tracking
ID and a signed, time-boxed registration link.

#### Scenario: Invitation creation returns a tracking ID and registration link
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation
- **THEN** the response includes a tracking ID and a registration link
  containing a signed token that expires after the configured TTL

#### Scenario: A retried creation request with the same idempotency key is not duplicated
- **WHEN** a caller retries `POST /invitations` with the same
  `Idempotency-Key` header and tenant context as an earlier successful
  request
- **THEN** exactly one invitation exists, and both requests receive the
  same response body

### Requirement: Public Multi-Step Self-Registration Submission
The system SHALL let the invited visitor complete their own registration —
primary contact, an ordered co-visitor list (group registrations only),
visit details, carried items, vehicles, and consent — through a public,
unauthenticated endpoint whose only authorization is possession of the
signed tracking token, submitting each visitor's and the primary contact's
ID proof as a separate file part matched by order.

#### Scenario: Individual registration accepts no additional visitors
- **WHEN** a self-registration submission has `registrationType: individual`
  and includes one or more entries in `visitors`
- **THEN** the request is rejected with 422

#### Scenario: Group registration requires at least one additional visitor
- **WHEN** a self-registration submission has `registrationType: group` and
  an empty `visitors` list
- **THEN** the request is rejected with 422

#### Scenario: Every visitor has a reachable contact method
- **WHEN** a visitor entry (primary contact or co-visitor) has neither
  `email` nor `phone` set
- **THEN** the request is rejected with 422

#### Scenario: ID proof files are validated by real content, not extension
- **WHEN** a file submitted as an ID proof does not match an allowed
  content type by its actual bytes (magic-byte sniffing), regardless of its
  filename or declared `Content-Type`
- **THEN** the request is rejected with 422 and nothing is stored

#### Scenario: A submission is accepted exactly once per invitation
- **WHEN** a self-registration submission is retried with the same
  `Idempotency-Key`, or attempted against an invitation already in
  `submitted` status
- **THEN** the retried/duplicate request does not create a second set of
  visitor/vehicle rows or re-trigger the confirmation notification

### Requirement: Tracking Lookup by ID Returns Everything the Visitor Submitted
`GET /invitations/track` by tracking ID SHALL return every field the
visitor supplied during self-registration — including visit details
(purpose, host, date, time, expected duration, department, additional
notes) and carried items (categories and description) — not only a subset,
since this lookup exists specifically for the visitor who submitted that
data to review it.

#### Scenario: Tracking-by-ID response includes visit and item detail
- **WHEN** a caller looks up a submitted invitation by tracking ID
- **THEN** the response includes `expectedDuration`, `departmentToVisit`,
  `additionalNotes`, and `carriedItems`/`carriedItemsDescription` matching
  exactly what was submitted, alongside the visitor/vehicle detail already
  returned

#### Scenario: Tracking by email stays minimally disclosing
- **WHEN** a caller looks up invitations by the primary contact's email
- **THEN** the response includes only the tracking ID and status per
  matching invitation — none of the visit-detail/carried-item/visitor/
  vehicle fields the tracking-ID lookup returns
