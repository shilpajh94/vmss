## Purpose

Baseline requirements for the `invitations` capability — a single
authenticated, branch-scoped call that creates a fully completed
pre-registration invitation (API-09), superseding the earlier two-phase
employee-creates/visitor-self-registers flow (API-09 + API-10), plus the
public tracking lookup (API-12).

## ADDED Requirements

### Requirement: Employee Creates a Fully Completed Invitation in a Single Call
The system SHALL let an authenticated, branch-scoped employee create a
complete invitation — `registrationType`, primary contact with ID proof, an
ordered co-visitor list (group registrations only) each with their own ID
proof, visit details, carried items, vehicles, and consent — in one
`multipart/form-data` call, submitting each visitor's and the primary
contact's ID proof as a separate file part matched by order, and generating a
human-readable expiry-bound tracking ID immediately.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload and ID-proof files
- **THEN** the response includes a tracking ID and `status: submitted`, with
  no further action required to complete the visit record

#### Scenario: A retried creation request with the same idempotency key is not duplicated
- **WHEN** a caller retries `POST /invitations` with the same
  `Idempotency-Key` header and tenant context as an earlier successful
  request
- **THEN** exactly one invitation exists, and both requests receive the same
  response body, with no duplicate visitor/vehicle rows or repeated
  confirmation notification

#### Scenario: Individual registration accepts no additional visitors
- **WHEN** a creation request has `registrationType: individual` and includes
  one or more entries in `visitors`
- **THEN** the request is rejected with 422

#### Scenario: Group registration requires at least one additional visitor
- **WHEN** a creation request has `registrationType: group` and an empty
  `visitors` list
- **THEN** the request is rejected with 422

#### Scenario: Every visitor has a reachable contact method
- **WHEN** a visitor entry (primary contact or co-visitor) has neither
  `email` nor `phone` set
- **THEN** the request is rejected with 422

#### Scenario: ID proof files are validated by real content, not extension
- **WHEN** a file submitted as an ID proof does not match an allowed content
  type by its actual bytes (magic-byte sniffing), regardless of its filename
  or declared `Content-Type`
- **THEN** the request is rejected with 422 and nothing is stored

### Requirement: Tracking Lookup by ID Returns Everything Captured at Creation
`GET /invitations/track` by tracking ID SHALL return every field captured
during creation — including visit details (purpose, host, date, time,
expected duration, department, additional notes) and carried items
(categories and description) — not only a subset, and SHALL always reflect
the invitation's final, fully detailed state, since creation itself completes
the visit record.

#### Scenario: Tracking-by-ID response includes visit and item detail
- **WHEN** a caller looks up an invitation by tracking ID
- **THEN** the response includes `expectedDuration`, `departmentToVisit`,
  `additionalNotes`, and `carriedItems`/`carriedItemsDescription` matching
  exactly what was captured at creation, alongside the visitor/vehicle detail
  already returned

#### Scenario: Tracking by email stays minimally disclosing
- **WHEN** a caller looks up invitations by the primary contact's email
- **THEN** the response includes only the tracking ID and status per matching
  invitation — none of the visit-detail/carried-item/visitor/vehicle fields
  the tracking-ID lookup returns

## REMOVED Requirements

### Requirement: Employee Creates a Single or Group Invitation Shell
**Reason**: Superseded by "Employee Creates a Fully Completed Invitation in a
Single Call" above — invitation creation no longer produces an incomplete
shell awaiting a separate registration step.
**Migration**: Callers creating an invitation with only `registrationType` and
a minimal primary contact must now submit the full payload (visitors, visit
details, carried items, vehicles, consents, and ID-proof files) as
`multipart/form-data` in the same call. There is no follow-up endpoint to
supply the remaining fields afterward.

### Requirement: Public Multi-Step Self-Registration Submission
**Reason**: The two-phase flow this requirement described is removed —
invitation creation now captures everything in one authenticated call, so
there is nothing left for a separate public, unauthenticated self-registration
step to do.
**Migration**: There is no replacement endpoint. Any integration that emailed
or texted a registration link to a visitor and waited for
`POST /invitations/{trackingToken}/register` must instead collect the full
payload up front and call `POST /invitations` directly. The signed invitation
token this endpoint relied on is no longer issued.
