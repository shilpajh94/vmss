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

### Requirement: A Retyped System Field's Submitted Value Is Validated Against Its Currently Configured Type
When a system field that Form Builder allows to be retyped (`fullName`,
`purposeOfVisit`, `departmentToVisit`, `licensePlate`, `expectedDuration`,
`additionalNotes`, `idProofType`, `vehicleType`) is currently configured
as an option-bearing type (`dropdown_select` or `checkbox_list`), a
submitted value for that field SHALL be validated against the calling
branch's currently published options for that field, the same way
`idProofType`/`vehicleType` submissions are already validated. When the
field is configured as a non-option-bearing type, the submitted value
SHALL be validated as ordinary free text (existing length/format rules),
unchanged from today. `host` is excluded from this requirement: its
submitted value (`hostNameOrEmail`) is always discarded before
persistence (an invitation's host is resolved exclusively through
delegation — see the `approvals` capability), so there is no stored value
for a retyped-`host`-field constraint to apply to.

#### Scenario: Submission matches a retyped field's configured options
- **WHEN** a branch's "Purpose of Visit" field has been retyped to
  `dropdown_select` with options `["Meeting", "Delivery", "Interview"]`
  and a visitor submits `purposeOfVisit: "Meeting"`
- **THEN** the submission is accepted

#### Scenario: Submission does not match a retyped field's configured options
- **WHEN** a branch's "Purpose of Visit" field has been retyped to
  `dropdown_select` with options `["Meeting", "Delivery", "Interview"]`
  and a visitor submits `purposeOfVisit: "Sightseeing"`
- **THEN** the submission is rejected with a validation error, mirroring
  the existing `idProofType`/`vehicleType` unknown-option rejection

#### Scenario: Submission for a field still configured as free text is unaffected
- **WHEN** a branch's "Purpose of Visit" field remains its default `text`
  type
- **THEN** any non-empty string within the existing length limit is
  accepted, exactly as before this change

### Requirement: Visitor and Primary Contact Registration Optionally Captures a Profile Photo
The system SHALL require a profile photo file for the primary contact on
every invitation-creation and walk-in-registration request — submitted as
a mandatory additional file part (`primaryContactPhotoFile`) alongside the
existing ID-proof file(s) in the same `multipart/form-data` request. A
request that omits the primary contact's photo SHALL be rejected with a
validation error before any invitation or registration record is created,
the same way an omitted primary-contact ID-proof file already is. The
system SHALL validate the uploaded photo's actual content against an
image-only allow-list (JPEG/PNG) — never the client-supplied content-type
or filename alone — and SHALL enforce a maximum upload size, consistent
with the existing ID-proof validation rules ("Every Visitor Has a
Reachable Contact and a Validated ID Proof"). Each co-visitor entry's
profile photo remains optional and order-matched to the visitor list the
same way co-visitor ID-proof files already are; omitting a co-visitor's
photo SHALL NOT cause the request to be rejected. Because
`POST /registrations/walk-in` accepts the identical payload/file contract
as `POST /invitations` (see the `registrations` capability), this
mandatory primary-contact photo capture applies to walk-in registrations
without any separate change to that endpoint. Every photo URL returned by
any invitation response (creation, detail, tracking, check-in, check-out,
list) SHALL be a fetchable HTTP URL an authenticated client can retrieve
the image content from, not merely a non-null string — per the
`file-storage` capability's requirement that a resolved reference is
usable by an HTTP client regardless of the active storage backend.

#### Scenario: Photo supplied and valid is stored and returned
- **WHEN** a creation request includes a valid JPEG or PNG photo for the
  primary contact
- **THEN** the request succeeds, the photo is stored, and the invitation's
  detail responses include a fetchable HTTP URL for it that an
  authenticated client can retrieve the image content from

#### Scenario: Missing primary contact photo is rejected
- **WHEN** a creation request omits the primary contact's photo file
- **THEN** the request is rejected with a validation error and no
  invitation or registration record is created

#### Scenario: Photo omitted does not affect creation
- **WHEN** a `group` creation request supplies no photo for one or more
  co-visitors (but does supply the now-mandatory primary contact photo)
- **THEN** the request succeeds, with no photo recorded for any co-visitor
  who didn't supply one

#### Scenario: Disguised executable submitted as a photo is rejected
- **WHEN** an uploaded photo file's real content does not match an allowed
  image format, regardless of its filename extension or declared content
  type
- **THEN** the system rejects the file and the overall request, creating no
  invitation record

#### Scenario: Oversized photo upload is rejected
- **WHEN** an uploaded photo file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload
  into memory

#### Scenario: Walk-in registration inherits the same optional photo capture
- **WHEN** a caller submits `POST /registrations/walk-in` with a photo for
  the primary contact and, optionally, one or more visitors, or omits a
  co-visitor's photo
- **THEN** the same validation and storage behavior applies as
  `POST /invitations`, since it submits the identical payload/file
  contract — including the mandatory primary contact photo requirement
  (see "Missing primary contact photo is rejected")

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
guidelines). The system SHALL record what was consented to and when. The
consent payload SHALL be bounded to the branch's configured set of consent
keys — a request MAY omit a non-required key but SHALL NOT introduce any key
outside that configured set, and the number of keys accepted SHALL be capped
to the size of the branch's configured consent set.

#### Scenario: Missing consent rejected
- **WHEN** a creation request has any required consent flag set to false or
  omitted
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Full consent accepted and timestamped
- **WHEN** a creation request has every required consent flag set to true
- **THEN** the system stores the acceptance along with the timestamp it was
  recorded

#### Scenario: Unknown consent key rejected
- **WHEN** a creation request's consent payload includes a key that is not
  in the branch's configured consent set
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Oversized consent payload rejected
- **WHEN** a creation request's consent payload contains more keys than the
  branch's configured consent set defines
- **THEN** the system rejects the request and creates no invitation record

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

### Requirement: QR Check-In Endpoint Transitions an Eligible Visitor to Checked-In
An invitation's check-in lifecycle SHALL be tracked by a `checkInStatus`
value of `unused`, `checked_in`, or `checked_out`, defaulting to `unused`.
`PATCH /api/v2/invitations/qr/{token}/check-in` SHALL transition an
invitation whose `checkInStatus` is `unused` or `checked_out` to
`checked_in`, recording `checkedInAt`, subject to the invitation being
`approved`, not watchlist-blocked (unless overridden), not scanned before
its scheduled visit date, and not expired (`expiresAt` has not already
passed). "Not scanned before its scheduled visit date" means: WHEN the
invitation has a `preferredVisitDate` set, THEN a scan is rejected if the
current date (tenant-local calendar day) is earlier than `preferredVisitDate`
— the comparison is date-only, so a scan is accepted at any time of day on
or after that date, up until `expiresAt`. WHEN the invitation has no
`preferredVisitDate` set, THEN this check is skipped entirely and only the
existing `expiresAt` gate applies. Calling this endpoint for an invitation
whose `checkInStatus` is already `checked_in` SHALL be rejected with 409 and
SHALL NOT change `checkInStatus` — the caller MUST call the check-out
endpoint instead. This endpoint does not toggle between check-in and
check-out; each action has its own endpoint (see "QR Check-Out Endpoint
Transitions a Checked-In Visitor to Checked-Out"). Repeated entry/exit
cycles are otherwise unrestricted — a visitor may enter and exit as many
times as the visit requires (e.g. leaving for lunch and returning, or moving
between buildings on a multi-building site); there is no terminal state
short of the invitation's own expiry.

#### Scenario: First scan checks the visitor in
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in`, `checkedInAt` is recorded,
  and the response indicates a successful check-in

#### Scenario: Re-entry after a prior check-out succeeds
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_out`, and the invitation is otherwise eligible
- **THEN** `checkInStatus` becomes `checked_in` again, `checkedInAt` is
  updated, and the response indicates a successful check-in

#### Scenario: Calling check-in while already checked in is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is already `checked_in`
- **THEN** the request is rejected with 409, `checkInStatus` is unchanged,
  and the response indicates the caller must use the check-out endpoint
  instead

#### Scenario: Entry scan after expiry is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out` and whose `expires_at` has already passed
- **THEN** the request is rejected as expired and `checkInStatus` is
  unchanged

#### Scenario: Entry scan before the scheduled visit date is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out`, whose `preferredVisitDate` is set, and whose
  `preferredVisitDate` is later than the current tenant-local calendar date
- **THEN** the request is rejected as too early, `checkInStatus` is
  unchanged, and the rejection is distinguishable from the expiry-rejection
  case

#### Scenario: Entry scan on the scheduled visit date succeeds regardless of time of day
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  equals the current tenant-local calendar date, at any time of day, and the
  invitation is otherwise eligible
- **THEN** the check-in succeeds — the scheduled-date check is date-only and
  does not additionally require a specific time of day

#### Scenario: Entry scan with no scheduled visit date set falls back to expiry-only gating
- **WHEN** this endpoint is called for an invitation whose `preferredVisitDate`
  is not set, and the invitation is otherwise eligible and not expired
- **THEN** the check-in succeeds exactly as it did before this change — the
  scheduled-date check is skipped entirely

### Requirement: QR Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out
`PATCH /api/v2/invitations/qr/{token}/check-out` SHALL transition an
invitation whose `checkInStatus` is `checked_in` to `checked_out`,
recording `checkedOutAt`. This transition SHALL NOT be subject to the
expiry check that governs check-in, so a visit that legitimately continues
past `expiresAt` can still be closed out. Calling this endpoint for an
invitation whose `checkInStatus` is `unused` or `checked_out` SHALL be
rejected with 409 and SHALL NOT change `checkInStatus`.

#### Scenario: Checking out a checked-in visitor succeeds
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_in`
- **THEN** `checkInStatus` becomes `checked_out`, `checkedOutAt` is
  recorded, and the response indicates a successful check-out

#### Scenario: Check-out succeeds even after expiry
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `checked_in` and whose `expires_at` has already passed
- **THEN** the check-out succeeds exactly as it would before expiry

#### Scenario: Calling check-out on a visitor who isn't checked in is rejected
- **WHEN** this endpoint is called for an invitation whose `checkInStatus`
  is `unused` or `checked_out`
- **THEN** the request is rejected with 409 and `checkInStatus` is
  unchanged

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
`expiresAt`, its current `checkInStatus`, and, for the primary contact and
for each visitor who has one on file, their captured profile photo (see
"Visitor and Primary Contact Registration Optionally Captures a Profile
Photo") — null for whichever of them has none. It SHALL additionally
include the primary contact's and each visitor's `idProofType`, and
resolved branch/building/department detail (see "QR Check-In, Check-Out,
and Detail Responses Surface Resolved Branch, Building, and Department"
below) — consistent with this endpoint's existing posture of disclosing
full registration detail to whoever holds the valid, signed QR token. It
SHALL NOT include an ID-proof document image/URL for the primary contact
or any visitor — that stays exclusive to the authenticated staff detail
view (`GET /invitations/{id}`), where `documents:view` can actually be
checked; there is no authenticated caller on this endpoint to gate a
document by. A rejected scan (invalid token, not approved,
watchlist-blocked, expired, or in a status the attempted action doesn't
allow) discloses none of this — only a generic failure message.

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

#### Scenario: Successful check-out response carries the same detail shape as check-in
- **WHEN** a QR check-out scan succeeds
- **THEN** the response includes the same visitor, host, visit, and
  timeline detail a successful check-in response would, reflecting the
  invitation's now-`checked_out` state

#### Scenario: Captured photos are included when present
- **WHEN** a QR check-in or check-out scan succeeds for an invitation
  whose primary contact and/or one or more visitors have a profile photo
  on file
- **THEN** the response includes each of their photos

#### Scenario: Missing photos are represented as null, not omitted or errored
- **WHEN** a QR check-in or check-out scan succeeds for an invitation
  where the primary contact or a visitor has no profile photo on file
- **THEN** that person's photo field is present and null, not omitted

#### Scenario: ID-proof type is present but the document image is not
- **WHEN** a QR check-in or check-out scan succeeds
- **THEN** the response includes the primary contact's and every
  visitor's `idProofType`, but no ID-proof document image/URL field is
  present for any of them

### Requirement: Primary Contact and Visitor ID-Proof Documents Are Surfaced Only to Callers Holding documents:view
The staff detail view (`GET /invitations/{id}`) SHALL include a resolved,
fetchable `idProofUrl` for the primary contact and for each visitor only
when the requesting caller holds the `documents:view` permission at the
invitation's branch, in addition to the `invitations:view` permission that
already gates the endpoint itself. A caller lacking `documents:view` SHALL
receive the same response with `idProofUrl` omitted (`null`) for the
primary contact and every visitor — the request SHALL NOT be rejected
solely for lacking `documents:view`. This is consistent with
`security-architecture.md` §4: access to a raw identity-document image is
its own permission, never implied by the ability to view the visitor
record it belongs to. The primary contact's and each visitor's
`idProofType` is not gated by `documents:view` and SHALL always be present
when the caller can reach the endpoint at all, since the type alone (e.g.
"Passport") does not expose document content. No other endpoint
(including the QR check-in/check-out endpoints — see "QR Check-In
Response Surfaces Full Invitation Detail" above) SHALL ever include the
ID-proof document image/URL, since none of them have an authenticated
caller to check `documents:view` against.

#### Scenario: Caller with documents:view sees the ID-proof document
- **WHEN** a caller holding both `invitations:view` and `documents:view` at
  the invitation's branch requests `GET /invitations/{id}`
- **THEN** the response includes a fetchable `idProofUrl` for the primary
  contact and for each visitor, alongside their `idProofType`

#### Scenario: Caller without documents:view does not see the ID-proof document
- **WHEN** a caller holding `invitations:view` but not `documents:view`
  requests `GET /invitations/{id}`
- **THEN** the request succeeds and includes every other field this
  capability defines, but `idProofUrl` is `null` for the primary contact
  and every visitor

#### Scenario: idProofType is always present regardless of documents:view
- **WHEN** any caller permitted to reach `GET /invitations/{id}` views the
  response
- **THEN** the primary contact's and every visitor's `idProofType` is
  present, independent of whether the caller holds `documents:view`

### Requirement: QR Check-In, Check-Out, and Detail Responses Surface Resolved Branch, Building, and Department
The staff detail view (`GET /invitations/{id}`) and the QR check-in/
check-out responses (`PATCH /api/v2/invitations/qr/{token}/check-in`,
`PATCH /api/v2/invitations/qr/{token}/check-out`) SHALL include the
invitation's resolved branch (name, code, address, city). The detail view
SHALL keep returning the raw `branchId` unchanged, in addition to this
resolved detail. When the invitation carries an optional `departmentId`
that resolves to a `Department` with a `floorId` that in turn resolves to
a `Building`, all three responses SHALL additionally include that
department's and building's name and code. When the invitation has no
`departmentId` on file, or its department has no `floorId`, the
response's `building` and `department` fields SHALL be `null` rather than
causing the request to fail — the existing free-text `departmentToVisit`
field is unaffected and remains present either way.

#### Scenario: Branch detail is always present
- **WHEN** a caller requests `GET /invitations/{id}` for any invitation,
  or a QR check-in or check-out scan succeeds
- **THEN** the response includes the invitation's branch name, code,
  address, and city

#### Scenario: Building and department are present when resolvable
- **WHEN** the invitation's `departmentId` resolves to a `Department`
  whose `floorId` resolves to a `Building`
- **THEN** all three responses include that building's and department's
  name and code

#### Scenario: Building and department are null when not resolvable
- **WHEN** the invitation has no `departmentId` on file, or its
  department's `floorId` is not set
- **THEN** the responses' `building` and `department` fields are `null`,
  and `departmentToVisit` (free text) is still present unchanged

### Requirement: Staff Check-In Has One Canonical Endpoint
The system SHALL expose exactly one staff/desk-facing endpoint for
transitioning an invitation into `checked_in` by an authenticated caller:
`PATCH /api/v2/invitations/{trackingId}/check-in`. The legacy `PATCH
/api/v1/invitations/{id}/check-in` endpoint SHALL be removed outright, not
merely deprecated. Staff check-out remains a separate endpoint (`PATCH
/api/v1/invitations/{id}/check-out`), unchanged by this requirement.

#### Scenario: Legacy v1 check-in route no longer exists
- **WHEN** a caller sends `PATCH /api/v1/invitations/{id}/check-in` for any
  invitation
- **THEN** the system returns 404, since the route itself is removed
- **AND** the check-in endpoint `PATCH /api/v2/invitations/{trackingId}/check-in` continues to function exactly as it did before this change

#### Scenario: Check-out is unaffected
- **WHEN** a caller with `invitations:checkin` at the invitation's branch
  calls `PATCH /api/v1/invitations/{id}/check-out` for a `checked_in`
  invitation
- **THEN** the check-out succeeds exactly as it did before this change

### Requirement: Staff Check-In Response Surfaces Full Invitation Detail
A successful response from `PATCH /api/v2/invitations/{trackingId}/check-in`
SHALL include every field the endpoint already returns today (`id`,
`trackingId`, `registrationType`, `source`, `status`, `visitorCategoryId`,
`hostId`, `expiresAt`, `submittedAt`, `approvedAt`, `currentApprovalStep`)
plus everything captured about the invitation at registration that the public
tracking lookup (`GET /invitations/track?trackingId=`) already returns for
the same invitation: the primary contact's full name, the resolved host's
display name, purpose of visit and department, the preferred visit
date/time and expected duration, additional notes, carried items, every
co-visitor on a group registration, and every declared vehicle. It SHALL
NOT include branch, creator, badge, or watchlist-override internals — those
remain exclusive to the staff detail view (`GET /invitations/{id}`). A
rejected check-in (invitation not found, not currently `approved`,
watchlist-blocked and not overridden) discloses none of this — only the
existing generic failure response. `PATCH
/api/v2/invitations/{trackingId}/check-in` is the sole staff/desk-facing
check-in endpoint — see "Staff Check-In Has One Canonical Endpoint" above.

#### Scenario: Successful check-in response includes visitor and host detail
- **WHEN** a caller with `invitations:checkin` at the invitation's branch
  successfully checks in an `approved` invitation via
  `PATCH /api/v2/invitations/{trackingId}/check-in`
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
`visitorCategoryId`, primary contact name, primary contact photo URL,
purpose of visit, expiry/submission timestamps) without the per-row
visitor/vehicle detail the single-invitation tracking lookup returns.

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
  status, `visitorCategoryId`, primary contact name, primary contact photo
  URL, purpose of visit, and expiry/submission timestamps, and does not
  include the per-visitor or per-vehicle detail that `GET /invitations/track`
  returns for a single invitation

#### Scenario: List row surfaces the primary contact's photo URL when one was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has a stored photo
- **THEN** that row includes a resolvable URL for the photo, matching the
  URL the tracking/detail endpoints return for the same invitation

#### Scenario: List row omits the photo field when no photo was captured
- **WHEN** a caller lists invitations via `GET /invitations` and an
  invitation's primary contact has no stored photo
- **THEN** that row's photo URL field is null, and the row is otherwise
  unaffected

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is any of:
(a) the invitation's resolved host (its `hostId`, once any of its approval
steps has been delegated to them — see "Invitation Output Surfaces the
Resolved Host as hostId") — regardless of that step's or the invitation's
current status;
(b) the delegate assigned to any of that invitation's approval steps (see
the `approvals` capability's "Current Step's Authorized Approver Delegates
It to a Specific Person") — regardless of that step's or the invitation's
current status; or
(c) currently holds, via branch-scoped role assignment at the invitation's
branch or company-wide, the role that the invitation's current pending
`InvitationApprovalStep` names (that step being role-identified) — i.e.,
the caller is one of the role-holders who could act on the
currently-pending step right now if no delegate had been assigned to it,
per the `approvals` capability's role-match authorization rule. Unlike that
authorization rule, clause (c) SHALL NOT require the step to be
undelegated: a role-holder keeps seeing the invitation via `relevantToMe`
even after the step has been delegated to a specific person, so that (e.g.)
every holder of the tenant's default host role keeps visibility into an
invitation after one of them delegates its `stepOrder` 0 step to the
resolved host, not just whichever one of them actually performed the
delegation.
Clause (c) only ever matches while the invitation is `submitted` with a
role-identified step currently pending; once that step is actually approved
or rejected (by its delegate or an override-permission holder), or the
invitation otherwise leaves `submitted`, a caller who only ever qualified
under (c) (never under (a) or (b)) no longer sees that invitation via
`relevantToMe`. Since every newly submitted invitation's `stepOrder` 0 step
is role-identified for the tenant's default host role (rather than
sometimes host-identified as before), clause (c) is what makes that
invitation visible to every front-office holder both before anyone
delegates it and after — clause (a) does not apply until a delegation
actually happens, but clause (c) keeps working across that transition, only
dropping off once the step itself is acted on; or
(d) has personally acted on (approved or rejected, i.e. is the `actedByUserId`
of) any of the invitation's approval steps, regardless of that step's or
the invitation's current status. Unlike (c), clause (d) never drops off:
once a caller has approved or rejected a step, that invitation stays in
their `relevantToMe` list for its entire lifecycle — e.g. Reception, having
approved the invitation's `stepOrder` 0 ownership step, keeps seeing it
through every later, differently-role-identified step and after final
approval/denial, not just while their own step was current
(reception-retains-visibility-and-delegation-after-own-step). Clause (d) is
keyed to the specific person who acted, not to a role: another holder of
Reception's role who never personally acted on that invitation does not
gain visibility from (d) — only (c), while their role's step is current,
covers them. This filter SHALL NOT require the caller to hold `invitations:view`,
and SHALL NOT be scoped by `X-Branch-ID` or the caller's authorized branches:
it is a personal worklist keyed to the caller's own identity and current
approval authority, not the branch-scoped admin listing the "Employee Lists
Invitations at Their Authorized Branches" requirement above describes.
`relevantToMe` SHALL compose with the existing `status`, `registrationType`,
and `source` filters and with pagination/sorting. A caller matching none of
(a)/(b)/(c)/(d) for any invitation SHALL receive an empty, successfully-paginated
result, not an error.

#### Scenario: Host sees their own invitation without invitations:view
- **WHEN** the user an invitation's ownership step was delegated to (its
  resolved `hostId`) requests `GET /invitations` with `relevantToMe=true`,
  and holds no `invitations:view` grant at that invitation's branch
- **THEN** the response includes that invitation

#### Scenario: Every front-office holder sees a freshly submitted invitation before anyone delegates it
- **WHEN** a user who holds the tenant's default host role at an invitation's
  branch, and to whom that invitation's `stepOrder` 0 step has not yet been
  delegated, requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, via clause (c)

#### Scenario: Delegate sees the invitation they were delegated
- **WHEN** a user who has been delegated one of an invitation's approval
  steps requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, whether or not the user
  holds `invitations:view` at its branch and regardless of that step's
  current status

#### Scenario: A role-holder sees an invitation whose current step needs their role
- **WHEN** a user who holds, via `UserBranchRole` at an invitation's branch,
  the `approverRoleId` role of that invitation's current pending
  role-identified step (and that step has no delegate assigned) requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, even though the user is
  neither the invitation's host nor a delegate — this closes the gap where
  such a user could only find the invitation via the branch-wide list

#### Scenario: A role-holder keeps seeing the invitation once someone else's delegation is assigned
- **WHEN** an invitation's current pending step (role-identified, matching a
  role the caller holds) is delegated to a different, specific user
- **THEN** the caller — though not that delegate, and no longer authorized
  to act on the step directly — still sees the invitation via
  `relevantToMe=true`, the same as every other holder of that role

#### Scenario: A role-holder loses visibility once the step is actually approved or rejected, unless they were the one who acted
- **WHEN** an invitation's current pending step, role-identified for a role
  the caller holds, is approved or rejected by a different holder of that
  role (or its delegate, or an override-permission holder)
- **THEN** the caller — who only ever qualified under clause (c) for that
  step, never as its host, its delegate, or the one who acted — no longer
  sees the invitation via `relevantToMe=true`, since that step is no longer
  the current pending step and clause (d) does not apply to them

#### Scenario: The caller who personally approved a step keeps seeing the invitation forever, via clause (d)
- **WHEN** a caller personally approves an invitation's current pending,
  role-identified step, and a later step (role-identified for a different
  role the caller does not hold) subsequently becomes current, is itself
  approved, and the invitation is fully approved
- **THEN** the caller continues to see the invitation via
  `relevantToMe=true` throughout — while the later step is current, after
  it is approved, and once the invitation itself is `approved` — because
  clause (d) does not depend on any step being current or on the
  invitation's own status

#### Scenario: Approving your own step also grants delegation authority over the very next step
- **WHEN** the caller from the previous scenario, instead of waiting, calls
  `POST /invitations/{id}/approval-steps/{stepId}/delegate` on the
  next step (now current, role-identified for a role the caller does not
  hold), naming a person who holds that step's role at the invitation's
  branch
- **THEN** the delegation succeeds (see the `approvals` capability's
  "Current Step's Authorized Approver Delegates It to a Specific Person",
  clause (d)) — the same clause (d) actor privilege that keeps the
  invitation visible to the caller also lets them route its next step
  onward

#### Scenario: A role-holder who is not currently authorized on the pending step sees nothing for it
- **WHEN** a user holds a role that does not match the invitation's current
  pending step's `approverRoleId` (e.g. the pending step is for a different
  role, or the invitation is not currently `submitted`)
- **THEN** that invitation is absent from the user's `relevantToMe=true`
  response, unless they separately qualify as its host or a delegate

#### Scenario: Caller who is neither host, delegate, nor actor sees nothing for that invitation
- **WHEN** a caller who is not the resolved host, has not been delegated
  any step, has not personally acted on any step, and does not hold the
  role of any invitation's current pending step requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who does not match (a), (b), (c), or (d) for any invitation
  requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch

### Requirement: Staff Looks Up a Visitor's Prefill Data by Email
`GET /invitations/lookup-by-email` SHALL accept a caller holding
`invitations:create` at a branch and an `email` query parameter, and SHALL
return a prefill payload (`fullName`, `phone`, `preferredContactMethod`,
`visitorCategoryId`, `idProofType`, `photoUrl`, `idProofUrl`) built from the
most recent non-deleted invitation, among the branches the caller is
authorized for, whose primary contact email matches the supplied `email`
case-insensitively. The response SHALL be `data: null` (`200`, not `404`)
when no matching invitation exists, consistent with the existing "no prior
visit is a normal case, not an error" convention. `photoUrl` SHALL be
resolved whenever a photo was captured, regardless of the caller's other
permissions — consistent with every other invitation response in this API
already exposing it ungated. `idProofUrl` SHALL be `null` unless the caller
additionally holds `documents:view` at the matched invitation's branch
(`security-architecture.md` §4) — `invitations:create` alone SHALL NOT be
sufficient to see the identity document image.

#### Scenario: Matching email returns the most recent invitation's prefill data
- **WHEN** a caller holding `invitations:create` at a branch requests
  `GET /invitations/lookup-by-email?email=jane@example.com`, and that
  branch has two invitations under that email, one older and one newer
- **THEN** the response's `data` reflects the newer invitation's
  `fullName`, `phone`, `preferredContactMethod`, `visitorCategoryId`, and
  `idProofType`

#### Scenario: Email match is case-insensitive
- **WHEN** an invitation on file has primary contact email
  `Jane@Example.com`, and a caller requests
  `GET /invitations/lookup-by-email?email=jane@example.com`
- **THEN** the response's `data` reflects that invitation

#### Scenario: No matching invitation returns null data, not an error
- **WHEN** a caller requests `GET /invitations/lookup-by-email` with an
  email that matches no invitation at any branch the caller is authorized
  for
- **THEN** the response is `200` with `data: null`

#### Scenario: A match at an unauthorized branch is not returned
- **WHEN** an invitation under the queried email exists only at a branch
  the caller does not hold `invitations:create` at
- **THEN** the response is `200` with `data: null`, not that other
  branch's data

#### Scenario: An explicit X-Branch-ID header narrows the lookup to that branch
- **WHEN** a caller authorized at multiple branches supplies an
  `X-Branch-ID` header naming one of them, and a matching invitation exists
  only at a different authorized branch
- **THEN** the response is `200` with `data: null`, since the lookup is
  narrowed to the named branch only

#### Scenario: Caller without invitations:create is rejected
- **WHEN** a caller holding only `invitations:view` (not
  `invitations:create`) at any branch requests this endpoint
- **THEN** the request is rejected with `403`

#### Scenario: Photo URL is always resolved when captured
- **WHEN** the most recent matching invitation has a photo on file, and
  the caller holds `invitations:create` but not `documents:view`
- **THEN** the response's `photoUrl` is a fetchable URL

#### Scenario: ID-proof URL is null without documents:view
- **WHEN** the most recent matching invitation has an ID-proof document on
  file, and the caller holds `invitations:create` but not `documents:view`
  at that invitation's branch
- **THEN** the response's `idProofType` is present but `idProofUrl` is
  `null`

#### Scenario: ID-proof URL is resolved with documents:view
- **WHEN** the most recent matching invitation has an ID-proof document on
  file, and the caller holds both `invitations:create` and
  `documents:view` at that invitation's branch
- **THEN** the response's `idProofUrl` is a fetchable URL

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
/registrations/walk-in`) SHALL accept optional `purposeId`, `durationId`, and
`departmentId` fields alongside its existing `purposeOfVisit`,
`expectedDuration` free-text fields and its optional `departmentToVisit`
free-text field. When any id is supplied, the system SHALL validate it
against the corresponding catalog/`Department` record, scoped to the
resolved tenant, and SHALL overwrite the paired free-text field with that
record's canonical display value before persisting, regardless of what
free-text value the request also supplied for that field. When an id is
omitted, its paired free-text field is accepted and stored exactly as
submitted, unchanged from today's behavior. `departmentToVisit` SHALL be
optional — a request may omit it (and `departmentId`) entirely, leaving the
invitation's department unset at creation, since a visitor or the staff
member creating the invitation on their behalf often does not yet know
which internal department is relevant; the field can be filled in later via
`PATCH /invitations/{id}/edit`. `VisitDetailsSubmit` SHALL NOT accept
`hostId` or `hostNameOrEmail` from either channel — the host is never
client-supplied at creation (see "Every New Invitation Is Owned by the
Tenant's Default Host Role at Creation"); a request that includes either
field SHALL have it ignored rather than rejected, so an un-updated client
does not start failing outright.

#### Scenario: Submission with no ids behaves exactly as before
- **WHEN** a caller submits `purposeOfVisit`, `expectedDuration`,
  `departmentToVisit` with no `purposeId`/`durationId`/`departmentId`
- **THEN** the invitation is created with exactly the submitted free-text
  values, identical to today's behavior

#### Scenario: Submission with an id overwrites free text with the catalog value
- **WHEN** a caller submits `departmentId` referencing an active department,
  along with a `departmentToVisit` string that does not match that
  department's name
- **THEN** the invitation is created with `departmentToVisit` set to the
  referenced department's actual name, not the client-supplied string

#### Scenario: Unknown or cross-tenant id is rejected
- **WHEN** a caller submits an id (`purposeId`, `durationId`, or
  `departmentId`) that does not resolve to an existing, active row in the
  resolved tenant's schema
- **THEN** the request is rejected with a validation error and no invitation
  is created

#### Scenario: Walk-in registration inherits the same optional fields
- **WHEN** a caller submits `POST /registrations/walk-in` with any of
  `purposeId`/`durationId`/`departmentId`
- **THEN** the same validation and free-text overwrite behavior applies,
  since it submits the identical `VisitDetailsSubmit` shape

#### Scenario: A supplied hostId or hostNameOrEmail is silently ignored
- **WHEN** a caller submits `POST /invitations` or `POST
  /registrations/walk-in` with `hostId` and/or `hostNameOrEmail` set (e.g. an
  un-updated client)
- **THEN** the invitation is created successfully, with those values ignored
  entirely — the invitation's host is never set from them, and no validation
  error is raised for supplying them

#### Scenario: Submission with no department succeeds and leaves it unset
- **WHEN** a caller submits `POST /invitations` or `POST
  /registrations/walk-in` with neither `departmentToVisit` nor
  `departmentId` set
- **THEN** the invitation is created successfully, with `departmentToVisit`
  null — no validation error is raised for omitting it, and no request-level
  default or placeholder value is substituted

#### Scenario: An unset department is later filled in via edit
- **WHEN** an invitation created with no department is subsequently edited
  via `PATCH /invitations/{id}/edit` to set `departmentToVisit`
- **THEN** the edit succeeds exactly as it would for any other eligible
  invitation, per the existing "Authorized Caller Edits Non-Personal
  Invitation Details" requirement

### Requirement: Invitation Output Surfaces the Resolved Host as hostId
`InvitationOut` and `InvitationDetailOut` SHALL include `hostId`, set to the
invitation's resolved host user id once one has been assigned, and null
before that. A host is assigned exclusively by delegating one of the
invitation's approval steps — the ownership step (`stepOrder` 0) or any
later step in its workflow chain — to a specific person, with the most
recently delegated step (of any `stepOrder`) determining the current
resolved host; see the `approvals` capability's "Current Step's Authorized
Approver Delegates It to a Specific Person" and "Delegating Any Step
Resolves/Updates the Invitation's Host" — never by anything supplied at
creation. `hostNameOrEmail` continues
to be surfaced alongside `hostId`, set to that same delegate's display name
once resolved, and null before that (this capability no longer accepts a
client-supplied `hostNameOrEmail` at creation to fall back to — see "Visit
Details Optionally Accept Catalog IDs Alongside Free Text").

#### Scenario: Resolved host is surfaced as hostId
- **WHEN** an invitation whose ownership step has been delegated to a
  specific person is fetched via `GET /invitations` (list) or `GET
  /invitations/{id}` (detail)
- **THEN** the response includes `hostId` set to that person's id, alongside
  `hostNameOrEmail` set to their display name

#### Scenario: Unresolved host leaves hostId null
- **WHEN** an invitation whose ownership step has not yet been delegated to
  a specific person is fetched (still pending for the owning role, or
  already acted on directly by a role-holder without delegating)
- **THEN** the response includes `hostId` and `hostNameOrEmail` as null

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

### Requirement: Every New Invitation Is Owned by the Tenant's Default Host Role at Creation
Every invitation submitted for approval (not auto-approved) SHALL have its
`stepOrder` 0 approval step created as role-identified for the tenant's
default host role (the standard `reception` role, unless a tenant has
reconfigured which role serves this purpose), unconditionally — regardless
of whether the invitation's category has any configured
`ApprovalWorkflowRule` rows. This replaces the prior behavior where
`stepOrder` 0 was host-identified when a client-supplied host resolved to a
user, and absent entirely when it did not. The category's own configured
rule chain (if any) keeps its rules' `stepOrder` values unchanged (by
convention starting at 1), unaffected by this default ownership step. This
requirement is defined in full in the `approvals` capability's "Submission
Snapshots the Category's Workflow Plus an Unconditional Ownership Step"; this entry
exists so the `invitations` capability's own requirements (push/email
fan-out, `relevantToMe`) can reference it without a forward dependency on
`approvals`.

#### Scenario: A newly submitted invitation always has a stepOrder 0 role step
- **WHEN** any invitation is submitted (not auto-approved), for a category
  with any number (including zero) of active `ApprovalWorkflowRule` rows
- **THEN** it has a `stepOrder` 0 `InvitationApprovalStep`, role-identified
  for the tenant's default host role, `pending`, ahead of any of the
  category's own configured steps

### Requirement: Submission Notifies the Owning Role via Push
WHEN `create_invitation` leaves an invitation `submitted` (not auto-approved),
the system SHALL dispatch a push notification to the newly-created
`stepOrder` 0 step's approver(s): every user holding that step's role (the
tenant's default host role) at the invitation's branch — except when that
role is the tenant's standard `admin` role (matched by name,
case-insensitively), which SHALL NOT receive a push notification. Every
submitted invitation has a `stepOrder` 0 step (see "Every New Invitation Is
Owned by the Tenant's Default Host Role at Creation"), so this dispatch is
unconditional for any non-auto-approved invitation.

#### Scenario: Submission notifies every holder of the owning role
- **WHEN** an invitation is submitted
- **THEN** every user holding the tenant's default host role at the
  invitation's branch receives a push notification that a new invitation
  awaits their triage

#### Scenario: Submission with an Admin-role owning role sends no push
- **WHEN** an invitation is submitted and a tenant has reconfigured its
  default host role to the tenant's standard `admin` role
- **THEN** no push notification is dispatched to anyone for the `stepOrder`
  0 step

### Requirement: Invitation Submission Notifies the Owning Role via Email
WHEN an invitation is submitted (not auto-approved), the system SHALL
dispatch an informational email to every active user holding the tenant's
default host role at the invitation's branch, stating that a new invitation
awaits triage — the tracking ID, visitor's name, and purpose of visit — in
addition to the existing push notification to the same recipients (see
"Submission Notifies the Owning Role via Push"). This is a new, additive
email channel: it does not replace or delay the visitor's own existing
submission/auto-approval notification, and a recipient with no reachable
email address is simply skipped for this dispatch without failing the
triggering request.

#### Scenario: Submission emails every holder of the owning role
- **WHEN** an invitation is submitted, and the tenant's default host role has
  two active users at the invitation's branch
- **THEN** both users receive an email stating a new invitation awaits
  triage, dispatched asynchronously without delaying the creation response

#### Scenario: A role-holder with no email is skipped without failing the dispatch
- **WHEN** one of the role's holders at the branch has no usable email
  address
- **THEN** that user is skipped for this email, the remaining holders still
  receive it, and the triggering request is unaffected

#### Scenario: Auto-approved creation sends no owning-role email
- **WHEN** an invitation is created and auto-approved per the Company's
  auto-approve setting (no approval steps are snapshotted at all)
- **THEN** no owning-role email is dispatched, consistent with "Auto-Approved
  Invitations Do Not Trigger a Submission Push"

### Requirement: Authorized Caller Edits Non-Personal Invitation Details
An authenticated, branch-scoped caller holding a new `invitations:edit`
permission at the invitation's branch SHALL be able to change, via `PATCH
/invitations/{id}/edit`, any of: `purposeOfVisit` (and `purposeId`),
`preferredVisitDate`, `preferredVisitTime`, `expectedDuration` (and
`durationId`), `departmentToVisit` (and `departmentId`), location/building,
and `additionalNotes` — on an invitation currently `submitted` or `approved`.
This endpoint SHALL NOT accept or change: the primary contact's or any
visitor's personal fields (name, email, phone, ID proof, photo),
`visitorCategoryId` (locked after creation — changing it would require
re-deriving the approval workflow, which this change does not support), or
the host (`hostId`/`hostNameOrEmail`) — host reassignment stays exclusively
the job of the `approvals` capability's delegation mechanism, so there is
exactly one way to change who the host is, not two. A request naming an
invitation that is not currently `submitted` or `approved` SHALL be rejected
with 409, following the same atomic-conditional-UPDATE pattern as the
existing `reschedule`/`extend` endpoints, and SHALL NOT change any field. An
unknown invitation id SHALL be rejected with 404; a caller without branch
access to an existing invitation SHALL be rejected with 403. A successful
edit SHALL dispatch a notification to the primary contact (and, if a host is
currently resolved, to the host) stating which visit details changed — the
same channel-routing rule (`preferredContactMethod`) the existing reschedule
notification already follows.

#### Scenario: Authorized edit changes multiple visit-detail fields at once
- **WHEN** a caller with `invitations:edit` at the invitation's branch edits
  a `submitted` invitation's `preferredVisitDate`, `expectedDuration`, and
  `additionalNotes` in one request
- **THEN** all three fields are updated, the invitation's other fields are
  unchanged, and the primary contact receives a notification describing the
  change

#### Scenario: Visitor personal fields and visitor category are rejected
- **WHEN** a request to `PATCH /invitations/{id}/edit` includes any of the
  primary contact's or a visitor's name/email/phone/ID-proof/photo fields, or
  `visitorCategoryId`
- **THEN** the request is rejected with a validation error and no field is
  changed

#### Scenario: Host fields are rejected
- **WHEN** a request to `PATCH /invitations/{id}/edit` includes `hostId` or
  `hostNameOrEmail`
- **THEN** the request is rejected with a validation error and no field is
  changed — host reassignment must go through the delegation endpoint
  instead

#### Scenario: Edit rejected for an ineligible status
- **WHEN** a caller attempts to edit an invitation that is `denied`,
  `checked_in`, or `checked_out`
- **THEN** the request is rejected with 409 and no field is changed

#### Scenario: Caller lacks invitations:edit
- **WHEN** a caller without `invitations:edit` at the invitation's branch
  attempts this endpoint
- **THEN** the request is rejected with 403 and no field is changed

#### Scenario: Unknown invitation id is rejected with 404
- **WHEN** a caller names an invitation id that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Edit while a host is resolved also notifies the host
- **WHEN** an authorized edit succeeds on an invitation whose ownership step
  has already been delegated to a specific host
- **THEN** both the primary contact and the resolved host receive a
  notification describing the change

### Requirement: Approval Notification Email Includes Full Visit and Host Detail
The email dispatched when an invitation is approved (directly, as the final
step of a workflow, or via a resolved-host approval step) SHALL be rendered
from the new branded HTML template (see the `email-notifications`
capability) and SHALL include: the tracking ID, visit date/time, expected
duration, location/building/department to visit, purpose of visit, and — the
gap this change closes — the resolved host's name and at least one
point-of-contact channel (the host's phone or email, whichever is on file)
when a host has been resolved by that point. WHEN no host has been resolved
by the time of approval (the owning role approved directly without
delegating), the email SHALL instead surface the branch's general front-desk
contact channel in the host/point-of-contact section, rather than omitting
that section or naming no one.

#### Scenario: Approval email with a resolved host includes their contact details
- **WHEN** an invitation whose ownership step was delegated to a specific
  host is approved
- **THEN** the visitor's approval email includes that host's name and at
  least one reachable contact channel, alongside the full visit detail

#### Scenario: Approval email with no resolved host falls back to the front-desk contact
- **WHEN** an invitation is approved directly by a holder of the tenant's
  default host role, without ever being delegated to a specific person
- **THEN** the visitor's approval email includes the branch's general
  front-desk contact channel in place of a named host, alongside the full
  visit detail

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

### Requirement: A Returning Primary Contact's Full Name Is Locked to Their Prior Invitation
Before creating an invitation, the system SHALL determine whether the
primary contact is "returning" using two keys, checked in this priority
order:
1. **Email match**: the new request's primary contact email is non-null and
   matches a prior invitation's primary contact email.
2. **Phone fallback**: the new request's primary contact email is null, and
   its primary contact phone matches a prior invitation's primary contact
   phone.

A "prior invitation" for either key includes one in any status —
`approved`, `submitted`, `denied`, `checked_in`, `checked_out`, or
expired. When more than one prior invitation matches a key, the most
recently created one is used.

WHEN an email match or a phone-fallback match is found, the system SHALL
persist that prior invitation's `primaryContactFullName` on the new
invitation, regardless of what value (if any) the new request submits for
it. WHEN no match is found — including when the new request's primary
contact email is non-null but does not match any prior invitation, even if
its phone would have matched a *different* prior invitation — the system
SHALL persist the submitted `primaryContactFullName` exactly as today, with
no change to existing behavior: a non-null, non-matching email always
means "treat as first-time," regardless of what the phone matches.

This lookup and substitution applies identically to `POST /invitations` and
`POST /registrations/walk-in`, since the latter is implemented as a direct
call into the same creation logic. No other field of the new invitation —
`primaryContactPhone` (in the email-match case), ID proof, photo,
`customFieldValues`, `visitorCategoryId`, visit details, carried items,
vehicles, consents, or co-visitors — is affected by this lookup; each is
taken from the new request exactly as it is today. A new `invitations` row
is still created for every invitation request, including this case — this
requirement never causes a request to update or reuse an existing row
instead of creating a new one.

#### Scenario: First time a contact is seen, submitted name is used
- **WHEN** an invitation is created with a primary contact email (or, if no
  email, phone) that has no prior invitation in the tenant's schema
- **THEN** the new invitation's `primaryContactFullName` is exactly the
  value submitted in the request

#### Scenario: Returning email overrides a different submitted name
- **WHEN** an invitation is created with a primary contact email that
  matches a prior invitation whose `primaryContactFullName` is "Priya
  Sharma", and the new request submits `primaryContactFullName` as "Priya
  S."
- **THEN** the new invitation is created with `primaryContactFullName`
  "Priya Sharma", not "Priya S.", and the response reflects the stored
  value

#### Scenario: Returning email's other fields are taken from the new request
- **WHEN** an invitation is created for a returning primary contact email,
  supplying a new phone number, a new `visitorCategoryId`, and new visit
  details
- **THEN** the new invitation stores the newly submitted phone number,
  visitor category, and visit details exactly as submitted — none of them
  are overridden by the prior invitation's values

#### Scenario: A denied or expired prior invitation still counts as a match
- **WHEN** a primary contact's only prior invitation for their email was
  `denied` or has since expired
- **THEN** a new invitation created with that same email still has its
  `primaryContactFullName` locked to that prior invitation's value

#### Scenario: No email submitted falls back to matching by phone
- **WHEN** an invitation is created with a primary contact that supplies a
  phone number but no email, and that phone matches a prior invitation's
  primary contact phone
- **THEN** the new invitation's `primaryContactFullName` is locked to that
  prior invitation's value, the same as an email match

#### Scenario: No email submitted and phone matches nothing is first-time
- **WHEN** an invitation is created with a primary contact that supplies a
  phone number but no email, and that phone matches no prior invitation
- **THEN** the submitted `primaryContactFullName` is used as-is, with no
  lock applied

#### Scenario: A genuinely new email is never overridden by a phone match
- **WHEN** an invitation is created with a primary contact email that does
  not match any prior invitation, even though its phone matches a *different*
  prior invitation belonging to a different email
- **THEN** the new invitation is created from the submitted payload as a
  first-time contact — `primaryContactFullName` and `primaryContactEmail`
  are exactly what was submitted, not locked to the phone-matched
  invitation's values

#### Scenario: A new invitations row is still created for a returning contact
- **WHEN** an invitation is created for a primary contact matched by email
  or by phone fallback
- **THEN** a new, distinct `invitations` row is created for this visit —
  the prior invitation's row is left completely unchanged, and the
  visitor's per-visit history still shows both invitations

#### Scenario: Walk-in registration applies the same lock
- **WHEN** a visitor submits `POST /registrations/walk-in` with a primary
  contact email matching a prior invitation, and a different full name than
  that prior invitation's stored value
- **THEN** the created registration's `primaryContactFullName` is the prior
  invitation's stored value, identical to the behavior for
  `POST /invitations`

#### Scenario: Co-visitors are never matched or locked
- **WHEN** a `group` invitation is created whose primary contact email
  matches a prior invitation, and one of its co-visitors shares an email
  with a person listed as a co-visitor on some earlier invitation
- **THEN** the co-visitor's `fullName` and other fields are stored exactly
  as submitted in this request — no lookup or locking is applied to any
  `invitation_visitors` entry

### Requirement: A Returning Primary Contact Matched by Phone Has Their Email Carried Forward
WHEN a new invitation's primary contact is matched to a prior invitation via
the phone fallback (no email submitted this visit — see "A Returning
Primary Contact's Full Name Is Locked to Their Prior Invitation"), the
system SHALL persist that prior invitation's `primaryContactEmail` on the
new invitation, rather than leaving it null.

#### Scenario: Phone-matched contact's email is populated from history
- **WHEN** an invitation is created with a primary contact that supplies
  only a phone number, and that phone matches a prior invitation whose
  stored `primaryContactEmail` is "priya@example.com"
- **THEN** the new invitation's `primaryContactEmail` is "priya@example.com",
  not null

#### Scenario: An email-matched contact's email is unaffected
- **WHEN** an invitation is created with a primary contact email that
  itself matches a prior invitation
- **THEN** the new invitation's `primaryContactEmail` is the submitted
  email, exactly as today — this requirement changes nothing for the
  email-match case, since the submitted and stored email are already the
  same
