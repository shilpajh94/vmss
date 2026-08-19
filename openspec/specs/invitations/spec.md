# Invitations Specification

## Purpose

Lets an authenticated, branch-scoped employee create a fully completed
visitor pre-registration — contact, co-visitors, visit details, carried
items, vehicles, and consent — in one call (API-09), dispatches a
confirmation with a check-in QR code (API-11), and lets any caller look up
an invitation's status without authentication, by tracking ID or by email
(API-12).

## Requirements

### Requirement: Employee Creates a Fully Completed Invitation in a Single Call
The system SHALL let an authenticated, branch-scoped employee holding
`invitations:create` create a complete invitation — `registrationType`,
primary contact with ID proof, an ordered co-visitor list (group
registrations only) each with their own ID proof, visit details, carried
items, vehicles, and consent — in one `multipart/form-data` call, submitting
each visitor's and the primary contact's ID proof as a separate file part
matched by order, and generating a human-readable tracking ID immediately.
There is no separate step to complete afterward.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload and ID-proof files
- **THEN** the response includes a tracking ID and `status: submitted`, with
  no further action required to complete the visit record

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an
  invitation
- **THEN** the system returns 403 and creates no invitation record

### Requirement: Invitation Has an Expiry-Bound Tracking Identity
Every created invitation SHALL receive a system-generated, human-readable
tracking ID (displayable and speakable, e.g. for a phone lookup) and an
expiry timestamp set at creation time, neither of which the request body can
override.

#### Scenario: Tracking ID is generated, not client-supplied
- **WHEN** an invitation is created
- **THEN** the response includes a system-generated tracking ID and an
  expiry timestamp, regardless of any value the request body supplied

### Requirement: Visitor List Matches Registration Type
The system SHALL require the visitor list to be empty when
`registrationType` is `individual` and to contain at least one visitor when
`registrationType` is `group`, and SHALL require the visitor list and the
uploaded co-visitor ID-proof files to match in count.

#### Scenario: Group submission with no co-visitors rejected
- **WHEN** a `group` invitation is created with an empty visitor list
- **THEN** the system rejects the request with a validation error

#### Scenario: Individual submission with a non-empty visitor list rejected
- **WHEN** an `individual` invitation is created with one or more entries in
  the visitor list
- **THEN** the system rejects the request with a validation error

#### Scenario: Visitor list and file count mismatch rejected
- **WHEN** the number of uploaded co-visitor ID-proof files does not match
  the number of entries in the visitor list
- **THEN** the system rejects the request with a validation error

### Requirement: Every Visitor Has a Reachable Contact and a Validated ID Proof
Every visitor entry (the primary contact and each co-visitor in a group)
SHALL provide at least one of email or phone, an ID proof type from the
supported set, and an accompanying ID proof file. The system SHALL validate
each uploaded file's actual content against an image/PDF allow-list, not
merely the client-supplied content type or file extension, and SHALL enforce
a maximum upload size. The system SHALL validate every visitor's ID proof
file before persisting any of them to storage, so that a request rejected
because one visitor's file fails validation leaves no other visitor's file
written to storage.

#### Scenario: Visitor with neither email nor phone rejected
- **WHEN** a visitor entry supplies neither an email nor a phone number
- **THEN** the system rejects the request with a validation error

#### Scenario: Disguised executable rejected
- **WHEN** an uploaded ID proof file's real content does not match an
  allowed image/PDF format, regardless of its filename extension or
  declared content type
- **THEN** the system rejects the file and the overall request

#### Scenario: Oversized upload rejected
- **WHEN** an uploaded ID proof file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload into
  memory

#### Scenario: Earlier visitor's file not persisted when a later visitor's file is rejected
- **WHEN** a group request's first visitor supplies a valid ID proof file
  and a later visitor's ID proof file fails content validation
- **THEN** the system rejects the entire request and does not write the
  first visitor's file to storage

### Requirement: Consent Is Mandatory and Recorded
An invitation SHALL be created only if the primary contact has accepted
every required consent (terms and conditions, data processing, and safety
guidelines). The system SHALL record what was consented to and when.

#### Scenario: Missing consent rejected
- **WHEN** a creation request has any required consent flag set to false or
  omitted
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Full consent accepted and timestamped
- **WHEN** a creation request has every required consent flag set to true
- **THEN** the system stores the acceptance along with the timestamp it was
  recorded

### Requirement: Carried Items and Vehicles Are Optional Structured Declarations
The system SHALL accept zero or more carried-item declarations (each an item
category plus an optional free-text description) and zero or more vehicle
declarations (each a vehicle type, license plate, make/model, and color),
and SHALL accept a request that declares neither.

#### Scenario: Request with no items or vehicles accepted
- **WHEN** a creation request omits carried items and vehicles entirely
- **THEN** the system accepts the request as long as all other requirements
  are met

#### Scenario: Multiple vehicles recorded
- **WHEN** a creation request lists more than one vehicle
- **THEN** the system stores each vehicle as a separate record linked to the
  invitation

### Requirement: Creation Requests Support Retried Submissions Without Duplication
`POST /invitations` SHALL accept an `Idempotency-Key` header. A retried
request carrying the same key and tenant context as an earlier successful
request SHALL return the original response instead of creating a second
invitation.

#### Scenario: A retried creation request with the same idempotency key is not duplicated
- **WHEN** a caller retries `POST /invitations` with the same
  `Idempotency-Key` header and tenant context as an earlier successful
  request
- **THEN** exactly one invitation exists, and both requests receive the same
  response body

### Requirement: Invitation Creation's Mandatory Fields Are Documented and Test-Verified
The system SHALL document, in `POST /invitations`'s `payload` field
description, which fields of each nested object (primary contact, each
visitor, visit details, carried items, each vehicle, consents) are mandatory
versus optional, derived from each schema's own required-field list rather
than duplicated by hand, and SHALL reject a request missing any top-level
mandatory field or containing an invalid enum value with a 422.

#### Scenario: Missing a required top-level field is rejected
- **WHEN** a creation request omits `registrationType`, `primaryContact`,
  `visitDetails`, or `consents` entirely
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Invalid enum value is rejected
- **WHEN** a creation request supplies a value for `idProofType`,
  `vehicleType`, or a carried-item category that is not one of the
  supported enum values
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: A vehicle or visitor missing its own required field is rejected
- **WHEN** an entry in `vehicles` omits `licensePlate`, or an entry in
  `visitors` omits `fullName`
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Documented required fields match the schema
- **WHEN** the `payload` field's description is compared against each
  nested Pydantic schema's own `model_json_schema()["required"]` list
- **THEN** every field the description calls mandatory is actually required
  by its schema, and vice versa

### Requirement: Invitation Creation's Multipart Payload Is Self-Documenting Without "Try It Out"
The system SHALL make the full JSON shape of `POST /invitations`'s `payload`
form field — for both the `individual` and `group` registration types —
readable directly from the field's own OpenAPI parameter description, so a
caller reading Swagger's Parameters table (before opening "Try it out" and
regardless of whether the rendering surface applies operation-level
multipart examples) can discover and construct a correct request.

#### Scenario: Payload description carries both registration-type examples
- **WHEN** the application's OpenAPI schema is generated
- **THEN** the `payload` parameter's description for `POST /invitations`
  contains an `individual` example and a `group` example, and each embedded
  example parses as valid JSON matching `InvitationCreate`

#### Scenario: File-upload parameters state their purpose and ordering
- **WHEN** the OpenAPI schema for `POST /invitations` is inspected
- **THEN** `primaryContactIdProofFile` and `visitorIdProofFiles` each carry a
  description identifying them as ID-proof image/PDF uploads, with the
  visitor-list one documented as order-matched to `payload.visitors`

### Requirement: Visit Confirmation With QR Code Is Dispatched on Creation
When an invitation is created, the system SHALL dispatch a visit-confirmation
notification — including a QR code encoding the invitation's tracking ID —
to the primary contact via their preferred contact method (email or SMS),
asynchronously and without delaying the creation response, and SHALL retry
transient delivery failures with backoff up to a configured limit.

#### Scenario: Creation response does not wait on delivery
- **WHEN** an invitation is created
- **THEN** the API responds with the invitation details before the
  confirmation has necessarily been delivered

#### Scenario: Delivery failure is retried and eventually surfaced
- **WHEN** the email/SMS provider is unavailable for a confirmation dispatch
- **THEN** the system retries with backoff and, if retries are exhausted,
  logs the failure with enough context to identify and manually resend the
  confirmation

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher
The system SHALL be provably capable of delivering the visit-confirmation
notification — including a valid QR-code image attachment — through actual
SMTP to a reachable mail catcher, not only asserted against a fake/recording
sender.

#### Scenario: Confirmation email arrives with a valid QR attachment
- **WHEN** the confirmation dispatch task runs for a created invitation
  using the real SMTP-backed sender
- **THEN** a message addressed to the invitation's primary contact, with the
  expected subject, and carrying a valid PNG attachment is observable
  through the mail catcher's own API

### Requirement: Public Lookup by Tracking ID Returns Everything Captured at Creation
Any caller SHALL be able to retrieve an invitation's full detail by
supplying its human-readable tracking ID, without authentication, subject to
rate limiting. The response SHALL include every field captured during
creation — including visit details (purpose, host, date, time, expected
duration, department, additional notes) and carried items (categories and
description) — not only a subset.

#### Scenario: Valid tracking ID returns full detail
- **WHEN** a caller requests the tracking endpoint with a tracking ID that
  exists
- **THEN** the response includes the invitation's status, `expectedDuration`,
  `departmentToVisit`, `additionalNotes`, `carriedItems`/
  `carriedItemsDescription`, and visitor/vehicle detail, matching exactly
  what was captured at creation

#### Scenario: Unknown tracking ID
- **WHEN** a caller requests the tracking endpoint with a tracking ID that
  does not exist
- **THEN** the system returns a not-found result

#### Scenario: Repeated lookups are throttled
- **WHEN** a caller exceeds the configured rate limit for the tracking
  endpoint
- **THEN** the system rejects further requests with the standard error
  envelope until the limit window resets

### Requirement: Public Lookup by Email Is Rate-Limited and Minimally Revealing
A caller SHALL also be able to look up invitations by the primary contact's
email address, without authentication, subject to rate limiting. This lookup
SHALL return only enough information (tracking ID and status) for the caller
to proceed to the tracking-ID lookup — it SHALL NOT return visit-detail,
carried-item, visitor, or vehicle information.

#### Scenario: Email lookup returns tracking IDs and status only
- **WHEN** a caller requests the tracking endpoint by email for an address
  with one or more invitations
- **THEN** the system returns each matching invitation's tracking ID and
  status, without visit-detail, carried-item, visitor, or vehicle
  information
