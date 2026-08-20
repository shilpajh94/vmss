## Purpose

Lets an employee invite a visitor ahead of their visit and lets that visitor complete their
own registration details (contact, co-visitors, visit info, items, vehicle, consent) through
a public link before they ever arrive, so reception has a verified, approval-ready record
waiting when the visitor shows up.

## ADDED Requirements

### Requirement: Employee Creates a Single or Group Invitation
An authenticated user holding `invitations:create` SHALL be able to create an invitation by
specifying `registrationType` (`individual` or `group`) and a primary contact (`fullName` and
at least one of `email`/`phone`, plus `preferredContactMethod`). The system SHALL persist the
invitation in `pending` status and SHALL NOT require visit purpose, host, identity documents,
carried items, vehicles, or consent at creation time — those are supplied later by the
visitor.

#### Scenario: Employee creates an individual invitation
- **WHEN** a user with `invitations:create` submits `registrationType: "individual"` with a
  primary contact's full name and email
- **THEN** the system creates an invitation in `pending` status scoped to the caller's branch
  and tenant

#### Scenario: Employee creates a group invitation
- **WHEN** a user with `invitations:create` submits `registrationType: "group"` with a primary
  contact
- **THEN** the system creates an invitation in `pending` status that will accept one or more
  additional visitors when the primary contact completes self-registration

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an invitation
- **THEN** the system returns 403 and creates no invitation record

### Requirement: Invitation Has an Expiry-Bound Tracking Identity
Every created invitation SHALL receive two identifiers: a human-readable tracking ID
(displayable and speakable, e.g. for a phone lookup) and a signed, time-boxed tracking token
(embedded in the registration link/QR) that a caller cannot forge or extend by supplying their
own value. Both SHALL be bound to an expiry timestamp set at creation time.

#### Scenario: Tracking ID and token are generated, not client-supplied
- **WHEN** an invitation is created
- **THEN** the response includes a system-generated tracking ID, a registration link
  containing the signed tracking token, and an expiry timestamp, none of which the request
  body can override

#### Scenario: Expired token rejected at self-registration
- **WHEN** a visitor submits self-registration using a tracking token past its expiry
  timestamp
- **THEN** the system rejects the submission with an error indicating the invitation has
  expired and does not create or update any visitor record

### Requirement: Public Self-Registration Submission
An unauthenticated visitor holding a valid, unexpired, not-yet-submitted tracking token SHALL
be able to submit, in one request: a primary contact (full name, email and/or phone,
preferred contact method, ID proof type, and an ID proof file), a visitor list, visit details
(purpose, host name or email, preferred date/time, expected duration, department to visit,
additional notes), carried items, vehicles, and consent acknowledgements. Token possession is
the sole authorization for this endpoint — the submitted contact fields become the
authoritative record for the invitation regardless of what the inviting employee entered at
creation.

#### Scenario: Individual registration submitted
- **WHEN** a visitor submits self-registration for a `registrationType: "individual"`
  invitation with their contact details, visit details, and accepted consents, and no entries
  in the visitor list
- **THEN** the system stores the submission, marks the invitation `submitted`, and treats the
  primary contact as the sole visitor

#### Scenario: Group registration submitted with co-visitors
- **WHEN** a visitor submits self-registration for a `registrationType: "group"` invitation
  with one or more entries in the visitor list, each with their own name and ID proof
- **THEN** the system stores the primary contact and every listed visitor against the same
  invitation and marks the invitation `submitted`

#### Scenario: Resubmission rejected
- **WHEN** a self-registration request is submitted a second time for a tracking token whose
  invitation is already `submitted`
- **THEN** the system rejects the request without modifying the stored submission

#### Scenario: Cancelled invitation rejected
- **WHEN** a self-registration request is submitted for a tracking token whose invitation has
  been cancelled
- **THEN** the system rejects the submission with an error indicating the invitation is no
  longer valid

### Requirement: Visitor List Matches Registration Type
The system SHALL require the submitted visitor list to be empty when `registrationType` is
`individual` and to contain at least one visitor when `registrationType` is `group`, and
SHALL reject a submission whose `registrationType` does not match the value set when the
invitation was created.

#### Scenario: Group submission with no co-visitors rejected
- **WHEN** a `group` invitation's self-registration is submitted with an empty visitor list
- **THEN** the system rejects the submission with a validation error

#### Scenario: Individual submission with a non-empty visitor list rejected
- **WHEN** an `individual` invitation's self-registration is submitted with one or more
  entries in the visitor list
- **THEN** the system rejects the submission with a validation error

#### Scenario: Registration type mismatch rejected
- **WHEN** a self-registration submission's `registrationType` differs from the value
  recorded when the invitation was created
- **THEN** the system rejects the submission with a validation error

### Requirement: Each Visitor Has at Least One Reachable Contact and an ID Proof
Every visitor entry (the primary contact and each co-visitor in a group) SHALL provide at
least one of email or phone, an ID proof type from the supported set (Aadhaar Card, Passport,
Driving License, Other), and an accompanying ID proof file. The system SHALL validate the
uploaded file's actual content against an image/PDF allow-list, not merely the client-supplied
content type or file extension, and SHALL enforce a maximum upload size.

#### Scenario: Visitor with neither email nor phone rejected
- **WHEN** a visitor entry supplies neither an email nor a phone number
- **THEN** the system rejects the submission with a validation error

#### Scenario: Disguised executable rejected
- **WHEN** an uploaded ID proof file's real content does not match an allowed image/PDF
  format, regardless of its filename extension or declared content type
- **THEN** the system rejects the file and the overall submission

#### Scenario: Oversized upload rejected
- **WHEN** an uploaded ID proof file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload into memory

### Requirement: Consent Is Mandatory and Recorded
A self-registration submission SHALL be accepted only if the visitor has accepted every
required consent (terms and conditions, data processing, and safety guidelines). The system
SHALL record what was consented to and when, against the invitation.

#### Scenario: Missing consent rejected
- **WHEN** a self-registration submission has any required consent flag set to false or
  omitted
- **THEN** the system rejects the submission and records no partial data

#### Scenario: Full consent accepted and timestamped
- **WHEN** a self-registration submission has every required consent flag set to true
- **THEN** the system stores the acceptance along with the timestamp it was recorded

### Requirement: Carried Items and Vehicles Are Optional Structured Declarations
The system SHALL accept zero or more carried-item declarations (each an item category plus an
optional free-text description) and zero or more vehicle declarations (each a vehicle type,
license plate, make/model, and color) as part of a self-registration submission, and SHALL
accept a submission that declares neither.

#### Scenario: Submission with no items or vehicles accepted
- **WHEN** a self-registration submission omits carried items and vehicles entirely
- **THEN** the system accepts the submission as long as all other requirements are met

#### Scenario: Multiple vehicles recorded
- **WHEN** a self-registration submission lists more than one vehicle
- **THEN** the system stores each vehicle as a separate record linked to the invitation

### Requirement: Invitation Link Dispatched on Creation
When an invitation is created, the system SHALL dispatch the registration link to the primary
contact via their preferred contact method (email or SMS) asynchronously, without delaying
the creation response, and SHALL retry transient delivery failures with backoff up to a
configured limit.

#### Scenario: Creation response does not wait on delivery
- **WHEN** an invitation is created
- **THEN** the API responds with the invitation details before the email/SMS has necessarily
  been delivered

#### Scenario: Delivery failure is retried and eventually surfaced
- **WHEN** the email/SMS provider is unavailable for an invitation dispatch
- **THEN** the system retries with backoff and, if retries are exhausted, logs the failure
  with enough context to identify and manually resend the invitation

### Requirement: Confirmation and QR Code Dispatched on Submission
When self-registration is submitted successfully, the system SHALL generate a QR code
encoding the invitation's tracking token and SHALL dispatch a confirmation (including the QR
code) to the primary contact via their preferred contact method, asynchronously.

#### Scenario: QR code generated on successful submission
- **WHEN** a self-registration submission is accepted
- **THEN** the system generates a QR code for that invitation's tracking token and includes it
  in the confirmation sent to the primary contact

#### Scenario: No QR code generated for a rejected submission
- **WHEN** a self-registration submission is rejected for any reason
- **THEN** the system does not generate a QR code or send a confirmation

### Requirement: Public Lookup by Tracking ID
Any caller SHALL be able to retrieve an invitation's status and visit summary by supplying its
human-readable tracking ID, without authentication, subject to rate limiting.

#### Scenario: Valid tracking ID returns status
- **WHEN** a caller requests the tracking endpoint with a tracking ID that exists
- **THEN** the system returns the invitation's current status (pending, submitted, expired,
  cancelled) and visit summary

#### Scenario: Unknown tracking ID
- **WHEN** a caller requests the tracking endpoint with a tracking ID that does not exist
- **THEN** the system returns a not-found result without revealing whether the ID was
  malformed or simply absent

### Requirement: Public Lookup by Email Is Rate-Limited and Minimally Revealing
A caller SHALL also be able to look up invitations by the primary contact's email address,
without authentication, subject to rate limiting. This lookup SHALL return only enough
information (tracking ID and status) for the caller to proceed to the tracking-ID lookup —
it SHALL NOT return other visitors' details, uploaded documents, or full visit details for
someone else's invitation.

#### Scenario: Email lookup returns tracking IDs and status only
- **WHEN** a caller requests the tracking endpoint by email for an address with one or more
  invitations
- **THEN** the system returns each matching invitation's tracking ID and status, without ID
  proof files, visitor list detail, or vehicle/item detail

#### Scenario: Repeated lookups are throttled
- **WHEN** a caller exceeds the configured rate limit for the tracking-by-email endpoint
- **THEN** the system rejects further requests until the limit window resets, and logs the
  trip at `WARNING`
