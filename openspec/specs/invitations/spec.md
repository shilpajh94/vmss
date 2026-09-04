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
`invitations:create` create a complete invitation — `registrationType`, a
`visitorCategoryId` referencing an active `VisitorCategory` in the resolved
tenant, primary contact with ID proof, an ordered co-visitor list (group
registrations only) each with their own ID proof, visit details, carried
items, vehicles, and consent — in one `multipart/form-data` call, submitting
each visitor's and the primary contact's ID proof as a separate file part
matched by order, and generating a human-readable tracking ID immediately.
`visitorCategoryId` is mandatory; a request omitting it or naming a category
that does not exist, is inactive, or belongs to a different tenant SHALL be
rejected with a validation error before any invitation is created. The
invitation's initial status is resolved from the tenant's auto-approve
setting rather than always being `submitted` — see "Invitation Creation's
Initial Approval State Follows the Company's Auto-Approve Setting" below.
Since nothing in the payload identifies a branch, the system SHALL resolve
the target branch from the `X-Branch-ID` header; a request supplying
neither the header nor any other branch signal SHALL be rejected with 400.

#### Scenario: Invitation creation returns a tracking ID with the invitation already complete
- **WHEN** an employee with `invitations:create` at their authorized branch
  creates an invitation with the full payload, a valid `visitorCategoryId`,
  and ID-proof files
- **THEN** the response includes a tracking ID, the `visitorCategoryId` that
  was submitted, and a status resolved per the company's auto-approve
  setting, with no further action required to complete the visit record when
  that status is `approved`

#### Scenario: Caller lacks permission
- **WHEN** a user without `invitations:create` attempts to create an
  invitation
- **THEN** the system returns 403 and creates no invitation record

#### Scenario: Missing branch signal is rejected
- **WHEN** a caller submits `POST /invitations` with no `X-Branch-ID` header
- **THEN** the request is rejected with 400, since the system has no other
  way to determine which branch the invitation belongs to

#### Scenario: Missing visitor category is rejected
- **WHEN** a creation request omits `visitorCategoryId`
- **THEN** the system rejects the request with a 422 validation error and
  creates no invitation record

#### Scenario: Unknown, inactive, or cross-tenant visitor category is rejected
- **WHEN** a creation request's `visitorCategoryId` does not resolve to an
  active `VisitorCategory` in the resolved tenant's schema
- **THEN** the system rejects the request with a validation error and
  creates no invitation record

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

### Requirement: Issued Badge Image Is Retrievable as a Fetchable URL
When a badge is issued or reprinted for an invitation, the response's
badge URL SHALL be a fetchable HTTP URL an authenticated client can
retrieve the badge image content from, not merely a non-null string —
consistent with the `file-storage` capability's requirement that a
resolved reference is usable by an HTTP client regardless of the active
storage backend.

#### Scenario: Issued badge URL is fetchable
- **WHEN** a badge is issued for an approved, checked-in invitation
- **THEN** the response's badge URL can be fetched by an authenticated
  client to retrieve the badge image content

#### Scenario: Reprinted badge URL is fetchable
- **WHEN** an already-issued badge is reprinted
- **THEN** the response's badge URL can be fetched by an authenticated
  client to retrieve the badge image content, whether or not it differs
  from the originally issued badge's URL

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
When an invitation is created, the system SHALL dispatch a visit-
confirmation notification to the primary contact via their preferred
contact method (email or SMS), asynchronously and without delaying the
creation response, and SHALL retry transient delivery failures with
backoff up to a configured limit. Whether that notification includes a QR
code depends on the invitation's resulting status — see "Invitation
Creation's Initial Approval State Follows the Company's Auto-Approve
Setting" below; a QR code is never included until the invitation is
`approved`.

#### Scenario: Creation response does not wait on delivery
- **WHEN** an invitation is created
- **THEN** the API responds with the invitation details before the
  confirmation has necessarily been delivered

#### Scenario: Delivery failure is retried and eventually surfaced
- **WHEN** the email/SMS provider is unavailable for a confirmation dispatch
- **THEN** the system retries with backoff and, if retries are exhausted,
  logs the failure with enough context to identify and manually resend the
  confirmation

### Requirement: Invitation Creation's Initial Approval State Follows the Company's Auto-Approve Setting
The system SHALL resolve a newly created invitation's initial status from
the tenant's `Company.autoApprovePreRegisteredVisitors` setting: `approved`
when it is enabled, or `submitted` (awaiting approval) when it is disabled
or when no `Company` profile is configured yet for the tenant. WHEN the
resulting status is `approved`, the system SHALL dispatch the approval
notification — the tracking ID and a QR code encoding an
authenticated-encrypted check-in token (see "QR Check-In Token Is
Encrypted and Tamper-Evident") — to the primary contact. WHEN the
resulting status is `submitted`, the system SHALL dispatch a
tracking-only notification — the tracking ID and current status, with no
QR code — and SHALL NOT dispatch the QR-bearing notification until the
invitation is later approved (see "A Submitted Invitation Can Be Manually
Approved").

#### Scenario: Auto-approve enabled creates an already-approved invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `true` and an employee creates an invitation
- **THEN** the invitation's status is `approved`, its `approvedAt`
  timestamp is set, and the dispatched notification includes the tracking
  ID and a QR code encoding an encrypted check-in token — not the plain
  tracking ID

#### Scenario: Auto-approve disabled creates an awaiting-approval invitation
- **WHEN** the tenant's `Company.autoApprovePreRegisteredVisitors` is
  `false` and an employee creates an invitation
- **THEN** the invitation's status is `submitted`, its `approvedAt` is
  unset, and the dispatched notification includes only the tracking ID and
  current status — no QR code

#### Scenario: No configured company profile defaults to awaiting approval
- **WHEN** an invitation is created for a tenant with no `Company` profile
  configured yet
- **THEN** the invitation is treated the same as auto-approve disabled —
  status `submitted`, tracking-only notification, no QR code

### Requirement: QR Check-In Token Is Encrypted and Tamper-Evident
The QR code issued for an approved invitation SHALL encode an
authenticated-encryption token of the invitation's internal id under a
server-side key — never the plain, human-readable tracking ID
and never the invitation id in cleartext. The token SHALL be generated
once, at the point the invitation becomes `approved`, and the same token
SHALL be reused for any later resend of the approval notification or
badge reprint for that invitation, rather than a new token being minted
on each resend. A token that fails authentication (invalid or tampered
ciphertext) SHALL be rejected without revealing which part of the token
was invalid.

#### Scenario: Token is generated once at approval
- **WHEN** an invitation transitions to `approved` (auto-approved at
  creation, or via manual approval)
- **THEN** the system generates one encrypted check-in token for that
  invitation and persists it alongside its rendered QR image

#### Scenario: Resending the approval notification reuses the issued token
- **WHEN** the approval notification for an already-approved invitation is
  resent
- **THEN** the QR code attached encodes the same token issued at approval
  time, not a newly generated one

#### Scenario: A tampered token is rejected
- **WHEN** the check-in endpoint receives a token whose ciphertext or
  authentication tag has been altered
- **THEN** the request is rejected as an invalid token, with no invitation
  detail disclosed

### Requirement: QR Check-In Drives a Cycling Checked-In/Checked-Out Lifecycle
An invitation's check-in lifecycle SHALL be tracked by a `checkInStatus`
value of `unused`, `checked_in`, or `checked_out`, defaulting to `unused`.
Scanning an invitation's QR check-in token SHALL toggle `checkInStatus`:
from `unused` or `checked_out` (the visitor is currently outside) to
`checked_in` on a valid scan, and from `checked_in` to `checked_out` on
the next valid scan — repeating for as many entry/exit cycles as the
visitor makes over the course of their visit (e.g. leaving for lunch and
returning, or moving between buildings on a multi-building site), not
limited to one round trip. There is no terminal state short of the
invitation's own expiry: a scan is never rejected merely because the
visitor has already completed an earlier visit/exit cycle.

#### Scenario: First scan checks the visitor in
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `unused`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in`, `checkedInAt` is
  recorded, and the response indicates a successful check-in

#### Scenario: A scan while checked in checks the visitor out
- **WHEN** the same QR check-in token is scanned again for an invitation
  whose `checkInStatus` is `checked_in`
- **THEN** `checkInStatus` becomes `checked_out`, `checkedOutAt` is
  recorded, and the response indicates a successful check-out

#### Scenario: A later scan re-admits a previously checked-out visitor
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_out`, and the invitation is otherwise
  eligible
- **THEN** `checkInStatus` becomes `checked_in` again, `checkedInAt` is
  updated, and the response indicates a successful check-in — exactly as
  it would from `unused`

### Requirement: QR Check-In Enforces Invitation Expiry on Every Entry
Every transition into `checked_in` — whether from `unused` (the first
entry) or from `checked_out` (a re-entry) — SHALL be rejected when the
invitation's `expires_at` has already passed at scan time. The
`checked_in` → `checked_out` transition SHALL NOT be subject to this
expiry check, so a visit that legitimately continues past `expires_at`
can still be closed out.

#### Scenario: First entry scan after expiry is rejected
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `unused` and whose `expires_at` is in the past
- **THEN** the request is rejected as expired and `checkInStatus` remains
  `unused`

#### Scenario: Re-entry scan after expiry is rejected
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_out` and whose `expires_at` is in the past
- **THEN** the request is rejected as expired and `checkInStatus` remains
  `checked_out`

#### Scenario: Exit scan after expiry still succeeds
- **WHEN** a QR check-in token is scanned for an invitation whose
  `checkInStatus` is `checked_in` and whose `expires_at` is in the past
- **THEN** the transition to `checked_out` succeeds

### Requirement: QR Check-In Response Surfaces Full Invitation Detail
A successful QR check-in response SHALL include everything captured
about the invitation at registration, matching what the public tracking
lookup (`GET /invitations/track?trackingId=`) already returns for the
same invitation, plus the QR-specific fields that lookup doesn't carry:
the visitor's contact details, the resolved host's display name, purpose
of visit and department, registration type and source, the preferred
visit date/time and expected duration, additional notes, carried items,
every co-visitor on a group registration, every declared vehicle, the
submitted/approved/checked-in/checked-out timeline, the invitation's
`expiresAt`, and its current `checkInStatus`. A rejected scan (invalid
token, not approved, watchlist-blocked, expired, or already completed)
discloses none of this — only a generic failure message, per the token
and lifecycle requirements above.

#### Scenario: Successful check-in response includes visitor and host detail
- **WHEN** a QR check-in scan succeeds
- **THEN** the response includes the visitor's name and contact details,
  the host's display name, purpose of visit, department, registration
  type and source, preferred visit date/time and expected duration,
  additional notes, carried items, the full co-visitor list, the full
  vehicle list, the relevant timeline timestamps, `expiresAt`, and
  `checkInStatus`

#### Scenario: A group registration's co-visitors are all present
- **WHEN** a QR check-in scan succeeds for a `group` registration with
  one or more co-visitors
- **THEN** the response's visitor list includes every co-visitor
  captured at registration, not just the primary contact

#### Scenario: Declared vehicles are present
- **WHEN** a QR check-in scan succeeds for an invitation that declared
  one or more vehicles at registration
- **THEN** the response's vehicle list includes every declared vehicle

### Requirement: Staff Check-In Response Surfaces Full Invitation Detail
A successful response from `PATCH /api/v1/invitations/{id}/check-in` SHALL
include every field the endpoint already returns today (`id`, `trackingId`,
`registrationType`, `source`, `status`, `visitorCategoryId`, `hostId`,
`expiresAt`, `submittedAt`, `approvedAt`, `currentApprovalStep`) plus
everything captured about the invitation at registration that the public
tracking lookup (`GET /invitations/track?trackingId=`) already returns for
the same invitation: the primary contact's full name, the resolved host's
display name, purpose of visit and department, the preferred visit
date/time and expected duration, additional notes, carried items, every
co-visitor on a group registration, and every declared vehicle. It SHALL
NOT include branch, creator, badge, or watchlist-override internals — those
remain exclusive to the staff detail view (`GET /invitations/{id}`). A
rejected check-in (invitation not found, not currently `approved`,
watchlist-blocked and not overridden) discloses none of this — only the
existing generic failure response.

#### Scenario: Successful check-in response includes visitor and host detail
- **WHEN** a caller with `invitations:checkin` at the invitation's branch
  successfully checks in an `approved` invitation via
  `PATCH /api/v1/invitations/{id}/check-in`
- **THEN** the response includes the primary contact's full name, the
  host's display name, purpose of visit, department, preferred visit
  date/time and expected duration, additional notes, carried items, the
  full co-visitor list, and the full vehicle list, in addition to the
  fields the response already carried

#### Scenario: A group registration's co-visitors are all present
- **WHEN** the check-in succeeds for a `group` registration with one or
  more co-visitors
- **THEN** the response's visitor list includes every co-visitor captured
  at registration, not just the primary contact

#### Scenario: Declared vehicles are present
- **WHEN** the check-in succeeds for an invitation that declared one or
  more vehicles at registration
- **THEN** the response's vehicle list includes every declared vehicle

#### Scenario: Individual registration has an empty visitor list
- **WHEN** the check-in succeeds for an `individual` registration (no
  co-visitors)
- **THEN** the response's visitor list is empty, not omitted or an error

#### Scenario: Response omits staff-only internals
- **WHEN** the check-in succeeds
- **THEN** the response does not include `branchId`, `createdByUserId`,
  badge information, or watchlist-override information — those remain
  exclusive to `GET /invitations/{id}`

#### Scenario: Rejected check-in discloses no invitation detail
- **WHEN** a check-in attempt is rejected (invitation not found, not
  currently `approved`, or watchlist-blocked and not yet overridden)
- **THEN** the response contains only the existing generic failure
  message, with no visitor, host, or visit detail

### Requirement: A Submitted Invitation Can Be Manually Approved
A caller holding `invitations:approve` at the invitation's own branch SHALL
be able to transition a `submitted` invitation to `approved` through this
endpoint only when the invitation has no approval steps snapshotted against
it (its `visitorCategoryId` had no active `ApprovalWorkflowRule` at
submission time, AND its host did not resolve to an active user at
submission time — see the `approvals` capability's "Submission Snapshots
the Category's Active Workflow Into Ordered Steps") — recording an
`approvedAt` timestamp, and the system SHALL then dispatch the approval
notification (tracking ID + QR code) to the primary contact — the same
notification an auto-approved invitation receives at creation. Calling this
endpoint for an invitation that does have snapshotted approval steps
(whether host-identified, role-identified, or both) SHALL be rejected with
409 and SHALL NOT change the invitation's status: that invitation must be
approved step by step through `POST /invitations/{id}/approval-
steps/{stepId}/approve`. Approving an invitation that is not currently
`submitted` SHALL be rejected with 409, leaving its status unchanged. An
invitation id that does not exist at all SHALL be rejected with 404. A
caller who lacks branch access to an invitation that does exist SHALL be
rejected with 403 — the same branch-authorization behavior `POST
/invitations` itself already applies when resolving a branch it doesn't
otherwise know from the request. The invitation's recorded `branchId` is
already-persisted historical data, not caller-supplied input, so branch
authorization for approval SHALL succeed based on that recorded id even if
the branch has since been soft-deleted — approval SHALL NOT fail with a
branch-not-found error for an invitation that otherwise exists and is
`submitted`. The transition itself SHALL be atomic: when two approval
requests for the same invitation are processed concurrently, exactly one
SHALL succeed and exactly one approval notification SHALL be dispatched —
the other SHALL observe the same 409 "not currently submitted" outcome the
sequential already-approved case produces, never a duplicate transition or
a duplicate notification.

#### Scenario: Manual approval transitions status and dispatches the QR notification
- **WHEN** a caller with `invitations:approve` at the invitation's branch
  approves a `submitted` invitation whose category has no configured
  approval workflow and whose host did not resolve to a user (no
  snapshotted steps)
- **THEN** the invitation's status becomes `approved`, `approvedAt` is set,
  and the approval notification (tracking ID + QR code) is dispatched to
  the primary contact

#### Scenario: Blanket approve rejected for a workflow-backed invitation
- **WHEN** a caller calls `POST /invitations/{id}/approve` for an invitation
  that has one or more snapshotted `InvitationApprovalStep` rows
- **THEN** the request is rejected with 409, the invitation's status is
  unchanged, and no notification is dispatched — the caller must approve
  through the step endpoint instead

#### Scenario: Blanket approve rejected when only a host-approval step is snapshotted
- **WHEN** a caller calls `POST /invitations/{id}/approve` for an invitation
  whose category has zero active `ApprovalWorkflowRule` rows but whose host
  resolved to a user at submission (one snapshotted host-identified step)
- **THEN** the request is rejected with 409, the invitation's status is
  unchanged, and no notification is dispatched — the caller must approve
  through the step endpoint instead

#### Scenario: Approving an already-approved invitation is rejected
- **WHEN** a caller attempts to approve an invitation whose status is
  already `approved`
- **THEN** the request is rejected with 409 and no second notification is
  dispatched

#### Scenario: Caller lacks invitations:approve
- **WHEN** a caller without `invitations:approve` attempts to approve a
  `submitted` invitation
- **THEN** the request is rejected with 403, the invitation's status is
  unchanged, and no notification is dispatched

#### Scenario: Unknown invitation id is rejected with 404
- **WHEN** a caller names an invitation id that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Caller lacks branch access to an existing invitation
- **WHEN** a caller with `invitations:approve` only at a different branch
  attempts to approve an invitation that exists at another branch
- **THEN** the request is rejected with 403, not 404 — the invitation's
  existence is not hidden, only the caller's access to act on it is denied

#### Scenario: Approving an invitation whose branch was soft-deleted after submission
- **WHEN** a caller with `invitations:approve` at the invitation's recorded
  branch approves a `submitted` invitation whose `branchId` refers to a
  `Branch` that has since been soft-deleted
- **THEN** the approval succeeds exactly as it would have before the branch
  was deleted — the invitation's status becomes `approved`, `approvedAt` is
  set, and the approval notification is dispatched

#### Scenario: Concurrent approval requests result in exactly one transition
- **WHEN** two approval requests for the same `submitted` invitation are
  processed concurrently, both otherwise authorized
- **THEN** exactly one request transitions the invitation to `approved` and
  dispatches the approval notification, and the other is rejected with 409
  as if the invitation were already approved

### Requirement: Approval-Step Rejection Denies the Invitation
Rejecting any snapshotted `InvitationApprovalStep` SHALL immediately
transition its invitation to the existing `denied` terminal state —
recording a denial reason and `deniedAt` timestamp, and dispatching the
existing denial notification — the same outcome as calling
`POST /invitations/{id}/deny` directly. Rejection is terminal: no step,
including one earlier in the sequence, becomes actionable again, and the
invitation cannot subsequently be approved. This applies regardless of
which step in the sequence is rejected — a rejection at step 1 of 3 has the
same terminal effect as a rejection at step 3 of 3.

#### Scenario: Rejecting any step denies the invitation
- **WHEN** an approver rejects a pending `InvitationApprovalStep`, at any
  `stepOrder`
- **THEN** the invitation's status becomes `denied`, a denial reason and
  `deniedAt` are recorded, and the denial notification is dispatched

#### Scenario: A denied invitation cannot later be approved
- **WHEN** a caller attempts to approve any step, or call the blanket
  approve endpoint, on an invitation already `denied` by a step rejection
- **THEN** the request is rejected with 409 and the invitation's status is
  unchanged

### Requirement: Reschedule Dispatches a Notification to the Primary Contact
WHEN a caller successfully reschedules an invitation via `PATCH
/invitations/{id}/reschedule`, the system SHALL dispatch a reschedule
notification to the primary contact, stating the invitation's tracking ID
and its new `preferredVisitDate`/`preferredVisitTime`. The notification
SHALL be sent via the primary contact's `preferredContactMethod` (`email`
sends an email, `sms` sends a text) — the same channel-routing rule the
creation, approval, and denial notifications already follow; group
registrations are notified the same way as individual ones, since only the
primary contact is ever notified for any invitation lifecycle event today.
The notification SHALL carry no QR code — a reschedule does not re-approve
the visit or invalidate a QR already issued. Dispatch SHALL happen
asynchronously (a background task), never inline in the request path, and
only after the reschedule is committed — a request rejected because the
invitation is not in a reschedulable status, or because the caller lacks
branch access, SHALL NOT dispatch any notification.

#### Scenario: Successful reschedule notifies the primary contact by email
- **WHEN** a caller with `invitations:reschedule` at the invitation's branch
  successfully reschedules an invitation whose primary contact's
  `preferredContactMethod` is `email`
- **THEN** an email is dispatched to the primary contact's email address,
  stating the tracking ID and the new `preferredVisitDate`/
  `preferredVisitTime`, with no QR code attached

#### Scenario: Successful reschedule notifies the primary contact by SMS when preferred
- **WHEN** a caller successfully reschedules an invitation whose primary
  contact's `preferredContactMethod` is `sms`
- **THEN** a text message is dispatched to the primary contact's phone
  number instead of an email, stating the same tracking ID and new
  date/time

#### Scenario: Rejected reschedule (ineligible status) dispatches no notification
- **WHEN** a caller attempts to reschedule an invitation that is not
  currently `submitted` or `approved` (e.g. already `checked_in`), and the
  request is rejected with 409
- **THEN** no reschedule notification is dispatched

#### Scenario: Rejected reschedule (no branch access) dispatches no notification
- **WHEN** a caller without branch access to the invitation attempts to
  reschedule it, and the request is rejected with 403
- **THEN** no reschedule notification is dispatched

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
creation — including `visitorCategoryId`, visit details (purpose, host,
date, time, expected duration, department, additional notes), and carried
items (categories and description) — not only a subset. WHEN the invitation
has one or more snapshotted approval steps and its status is `submitted`,
the response SHALL additionally include the current pending step's
`stepOrder`, `approverRoleId`, and the total number of steps, so a caller
can be shown progress (e.g. "step 2 of 3") instead of a single undated
"awaiting approval" status. WHEN the invitation has no snapshotted steps, or
is no longer `submitted`, this step-progress information SHALL be omitted
(null) rather than fabricated.

#### Scenario: Valid tracking ID returns full detail
- **WHEN** a caller requests the tracking endpoint with a tracking ID that
  exists
- **THEN** the response includes the invitation's status, `visitorCategoryId`,
  `expectedDuration`, `departmentToVisit`, `additionalNotes`,
  `carriedItems`/`carriedItemsDescription`, and visitor/vehicle detail,
  matching exactly what was captured at creation

#### Scenario: Workflow-backed invitation exposes current step progress
- **WHEN** a caller looks up a `submitted` invitation that has snapshotted
  approval steps
- **THEN** the response includes the current pending step's `stepOrder`,
  `approverRoleId`, and the total step count

#### Scenario: Non-workflow invitation omits step progress
- **WHEN** a caller looks up an invitation with no snapshotted approval
  steps, or one that is no longer `submitted`
- **THEN** the response's step-progress fields are null

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

### Requirement: Employee Lists Invitations at Their Authorized Branches
The system SHALL let an authenticated caller holding `invitations:view` list
invitations, paginated, sorted, and filterable by `status`,
`registrationType`, and `source`. A request supplying `X-Branch-ID` SHALL be
narrowed to that one branch, rejected with 404/403 the same way other
branch-scoped endpoints reject an unknown or unauthorized branch id. A
request omitting `X-Branch-ID` SHALL return invitations across every branch
the caller holds `invitations:view` at, rejected with 403 only if that set
is empty. Each row in the response SHALL include enough detail to identify
and triage the invitation (tracking ID, registration type, source, status,
`visitorCategoryId`, primary contact name, purpose of visit, expiry/
submission timestamps) without the per-row visitor/vehicle detail the
single-invitation tracking lookup returns.

#### Scenario: Caller with company-wide access lists across all their branches
- **WHEN** a caller with `invitations:view` granted company-wide requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the response includes invitations from every branch, paginated
  per the requested page/pageSize

#### Scenario: X-Branch-ID narrows the result to one branch
- **WHEN** a caller with `invitations:view` at a specific branch requests
  `GET /invitations` with that branch's `X-Branch-ID`
- **THEN** the response includes only that branch's invitations

#### Scenario: Unauthorized branch id rejected
- **WHEN** a caller requests `GET /invitations` with an `X-Branch-ID` for a
  branch they are not authorized to view invitations at
- **THEN** the system returns 403 and no invitation data

#### Scenario: Caller lacks permission everywhere
- **WHEN** a caller with no `invitations:view` grant at any branch requests
  `GET /invitations` without an `X-Branch-ID` header
- **THEN** the system returns 403

#### Scenario: Filtering by status, registration type, and source
- **WHEN** a caller requests `GET /invitations` with `status`,
  `registrationType`, and/or `source` query parameters set
- **THEN** the response includes only invitations matching every supplied
  filter

#### Scenario: Sorting is validated against a whitelist
- **WHEN** a caller requests `GET /invitations` with a `sortBy` value that
  is not one of the endpoint's documented sortable fields
- **THEN** the system rejects the request with a validation error rather
  than passing the value through to the database

#### Scenario: List rows omit visitor and vehicle detail
- **WHEN** a caller lists invitations via `GET /invitations`
- **THEN** each row includes tracking ID, registration type, source,
  status, `visitorCategoryId`, primary contact name, purpose of visit, and
  expiry/submission timestamps, and does not include the per-visitor or
  per-vehicle detail that `GET /invitations/track` returns for a single
  invitation

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is either (a) the user identified by that invitation's
`stepOrder` 0 host-identified `InvitationApprovalStep` (i.e. the snapshotted
host), or (b) the delegate assigned to any of that invitation's approval
steps (see the `approvals` capability's "Host Delegates the Step Following
Their Own to a Specific Person" requirement) — regardless of that step's or
the invitation's current status. This filter SHALL NOT require the caller
to hold `invitations:view`, and SHALL NOT be scoped by `X-Branch-ID` or the
caller's authorized branches: it is a personal worklist keyed to the
caller's own identity, not the branch-scoped admin listing the "Employee
Lists Invitations at Their Authorized Branches" requirement above
describes. `relevantToMe` SHALL compose with the existing `status`,
`registrationType`, and `source` filters and with pagination/sorting,
narrowing the relevant-to-me set the same way those filters narrow the
branch-scoped list. A caller with no invitations where they are host or
delegate SHALL receive an empty, successfully-paginated result, not an
error.

#### Scenario: Host sees their own invitation without invitations:view
- **WHEN** the user identified as the host of an invitation (its
  `stepOrder` 0 step's `approverUserId`) requests `GET /invitations` with
  `relevantToMe=true`, and holds no `invitations:view` grant at that
  invitation's branch
- **THEN** the response includes that invitation

#### Scenario: Delegate sees the invitation they were delegated
- **WHEN** a user who has been delegated one of an invitation's approval
  steps requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, whether or not the user
  holds `invitations:view` at its branch and regardless of that step's
  current status

#### Scenario: Caller who is neither host nor delegate sees nothing for that invitation
- **WHEN** a caller who is not the snapshotted host and has not been
  delegated any step of a given invitation requests `GET /invitations` with
  `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who is neither host nor delegate on any invitation
  requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch

### Requirement: A Confirmation or Approval Email Dispatch Failure Is Logged With Enough Detail To Diagnose
WHEN the configured SMTP gateway rejects or fails to send a visit-
confirmation, tracking-only, or approval notification email, the system
SHALL log the configured SMTP host and port and the underlying exception's
type and message, in addition to the tenant and invitation context already
logged on retry exhaustion. This SHALL NOT change the client-facing
response — invitation creation and approval continue to respond
successfully regardless of dispatch outcome (dispatch is asynchronous) —
and the log line SHALL NOT include the recipient's email address, phone
number, or any OTP/credential value.

#### Scenario: An email dispatch failure logs host, port, and exception detail
- **WHEN** the configured SMTP gateway rejects or fails to send a
  confirmation, tracking-only, or approval notification email
- **THEN** the log line for that failure includes the configured SMTP host
  and port and the underlying exception's type and message

#### Scenario: Dispatch-failure logging never includes the recipient identifier or credentials
- **WHEN** an email dispatch failure is logged
- **THEN** the log line contains no recipient email address, phone number,
  or SMTP credential value

#### Scenario: Retry and exhaustion behavior is unchanged by the added logging
- **WHEN** an email dispatch fails, before and after this logging change
- **THEN** the task retries with the same backoff and maximum-retry policy,
  and the response returned to the caller that created or approved the
  invitation is unaffected

### Requirement: Visit Details Optionally Accept Catalog IDs Alongside Free Text
`VisitDetailsSubmit` (used by both `POST /invitations` and `POST
/registrations/walk-in`) SHALL accept optional `purposeId`, `hostId`,
`durationId`, and `departmentId` fields alongside its existing
`purposeOfVisit`, `hostNameOrEmail`, `expectedDuration`, `departmentToVisit`
free-text fields. When any id is supplied, the system SHALL validate it
against the corresponding catalog/`Department`/`User` record, scoped to the
resolved tenant, and SHALL overwrite the paired free-text field with that
record's canonical display value before persisting, regardless of what
free-text value the request also supplied for that field. When an id is
omitted, its paired free-text field is accepted and stored exactly as
submitted, unchanged from today's behavior.

#### Scenario: Submission with no ids behaves exactly as before
- **WHEN** a caller submits `purposeOfVisit`, `hostNameOrEmail`,
  `expectedDuration`, `departmentToVisit` with no `purposeId`/`hostId`/
  `durationId`/`departmentId`
- **THEN** the invitation is created with exactly the submitted free-text
  values, identical to today's behavior

#### Scenario: Submission with an id overwrites free text with the catalog value
- **WHEN** a caller submits `departmentId` referencing an active department,
  along with a `departmentToVisit` string that does not match that
  department's name
- **THEN** the invitation is created with `departmentToVisit` set to the
  referenced department's actual name, not the client-supplied string

#### Scenario: Unknown or cross-tenant id is rejected
- **WHEN** a caller submits an id (`purposeId`, `hostId`, `durationId`, or
  `departmentId`) that does not resolve to an existing, active row in the
  resolved tenant's schema
- **THEN** the request is rejected with a validation error and no invitation
  is created

#### Scenario: Walk-in registration inherits the same optional fields
- **WHEN** a caller submits `POST /registrations/walk-in` with any of
  `purposeId`/`hostId`/`durationId`/`departmentId`
- **THEN** the same validation and free-text overwrite behavior applies,
  since it submits the identical `VisitDetailsSubmit` shape

### Requirement: Invitation Output Surfaces the Resolved Host as hostId
`InvitationOut` and `InvitationDetailOut` SHALL include `hostId`, set to the
invitation's resolved host user id when submission resolved `hostId` or
`hostNameOrEmail` to an active user, and null when it did not — alongside
the existing free-text `hostNameOrEmail`, unchanged.

#### Scenario: Resolved host is surfaced as hostId
- **WHEN** an invitation whose host resolved to an active user at
  submission is fetched via `GET /invitations` (list) or `GET
  /invitations/{id}` (detail)
- **THEN** the response includes `hostId` set to that user's id, alongside
  the existing `hostNameOrEmail`

#### Scenario: Unresolved host leaves hostId null
- **WHEN** an invitation created with only a free-text `hostNameOrEmail`
  that did not resolve to an active user is fetched
- **THEN** the response includes `hostId` as null, with `hostNameOrEmail`
  unchanged

### Requirement: Default-Tenant Misconfiguration on Tracking Lookup Is Reported and Logged as a Server Error
Public lookup by tracking ID resolves a single server-configured default
tenant (there being no caller-supplied tenant identifier on this
unauthenticated endpoint). When that default tenant does not resolve —
because no tenant matches the configured slug, or the matching tenant is
inactive — this is a server-side configuration gap, not a property of the
caller's request, and SHALL be logged at `ERROR` distinguishing "no such
tenant" from "tenant inactive", consistent with the equivalent requirement
already defined for walk-in registration's default-tenant/branch fallback.

#### Scenario: Unconfigured default tenant is logged as a server misconfiguration
- **WHEN** a tracking-ID lookup is made and the configured default tenant
  slug does not match any tenant, or matches one that is inactive
- **THEN** the rejection is logged at `ERROR`
- **AND** the log distinguishes whether no such tenant row exists at all
  versus the row exists but is inactive, so an operator can tell the fix
  from the log alone

#### Scenario: Client-facing response is unchanged
- **WHEN** the default tenant fails to resolve for a tracking-ID lookup
- **THEN** the caller receives the same not-found response this endpoint
  already returns for that condition today — only the server-side log
  gains the `ERROR`-level detail

### Requirement: Invitation Approval, Denial, Reschedule, Check-In, and Check-Out Notify the Host via Push
When an invitation with a resolved host (`host_id` present) is approved
(directly, or as the final step of a multi-step workflow), denied (directly,
or via a rejected step), rescheduled, checked in, or checked out, the system
SHALL dispatch a push notification to that host user, in addition to the
visitor's existing email/SMS notification where one already exists for that
action. An invitation with no resolved host SHALL skip the push dispatch for
these actions without failing the triggering request.

#### Scenario: Approval notifies the host
- **WHEN** an invitation with a resolved host is approved (via
  `POST /invitations/{id}/approve` or as the final approval step)
- **THEN** the host user receives a push notification, and the visitor still
  receives their existing approval email/SMS unchanged

#### Scenario: Denial notifies the host
- **WHEN** an invitation with a resolved host is denied (directly, or via a
  rejected approval step)
- **THEN** the host user receives a push notification stating the invitation
  was denied

#### Scenario: Reschedule notifies the host
- **WHEN** an invitation with a resolved host has its preferred visit
  date/time changed via the reschedule endpoint
- **THEN** the host user receives a push notification stating the new
  date/time, alongside the visitor's existing reschedule email/SMS

#### Scenario: Check-in and check-out notify the host
- **WHEN** an invitation with a resolved host is checked in, and later when
  it is checked out
- **THEN** the host user receives a push notification for each event

#### Scenario: No resolved host means no push, and the request still succeeds
- **WHEN** any of the actions above completes for an invitation whose
  `host_id` never resolved
- **THEN** the action's own HTTP response is unaffected and no push
  notification is dispatched for that action

### Requirement: Invitation Submission Notifies the Approval Workflow's First Approver(s) via Push
When `create_invitation` leaves an invitation `submitted` (not auto-approved)
with at least one approval step, the system SHALL dispatch a push
notification to the newly-created first (`step_order` 0) step's
approver(s): the resolved host if the step is host-identified, or every
user holding the step's role at the invitation's branch if role-identified
— except when that role is the tenant's standard `admin` role (matched by
name, case-insensitively), which SHALL NOT receive a push notification.

#### Scenario: Submission with a host-identified first step
- **WHEN** an invitation is submitted and its host resolves, giving it an
  implicit host-identified step 0
- **THEN** the host user receives a push notification that a new invitation
  awaits their approval

#### Scenario: Submission with a role-identified first step
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 for a role other
  than the tenant's standard `admin` role (e.g. Reception, Security, or a
  tenant-defined custom role)
- **THEN** every user holding that role at the invitation's branch receives
  a push notification that a new invitation awaits their approval

#### Scenario: Submission with an Admin-role first step sends no push
- **WHEN** an invitation is submitted with no resolved host, and its
  category's workflow gives it a role-identified step 0 for the tenant's
  standard `admin` role
- **THEN** no push notification is dispatched to anyone for that step

### Requirement: Auto-Approved Invitations Do Not Trigger a Submission Push
An invitation created while the tenant's Company profile auto-approves
pre-registered visitors never has approval steps, so its creation SHALL NOT
dispatch a "submitted, awaiting your approval" push to anyone — only the
visitor's existing auto-approval email/SMS fires.

#### Scenario: Auto-approve tenant, no staff push on creation
- **WHEN** an invitation is created for a tenant whose Company profile has
  `auto_approve_pre_registered_visitors` enabled
- **THEN** no approval-step push notification is dispatched, and the visitor
  still receives their existing approval-confirmation email/SMS
