# Visitor Return Visit Specification

## Purpose

Lets a visitor who has verified an email or phone number via the existing OTP
flow retrieve their own prior visit history and a prefill payload for a new
registration, without creating any authenticated user/RBAC identity.

## Requirements

### Requirement: Returning-Visitor Lookup Is Keyed Solely to a Verified-Contact Proof
The system SHALL expose an unauthenticated endpoint that accepts only a
signed `identity_verified` proof token (issued by the `identity-verification`
capability's OTP-verify step) and SHALL derive the identifier to look up
exclusively from that token's claims — never from a client-supplied email or
phone value in the request body or query string. A request presenting no
proof token, an expired one, or one that fails signature verification SHALL
be rejected with 401 before any lookup is attempted.

#### Scenario: Valid proof token drives the lookup
- **WHEN** a caller presents a valid, unexpired `identity_verified` proof
  token obtained from a prior successful OTP verification
- **THEN** the system looks up visit history and prefill data for exactly
  the identifier and channel embedded in that token's claims

#### Scenario: Missing proof token is rejected
- **WHEN** a caller requests the returning-visitor lookup with no proof
  token
- **THEN** the request is rejected with 401 and no lookup is performed

#### Scenario: Expired or tampered proof token is rejected
- **WHEN** a caller presents a proof token that has expired or fails
  signature verification
- **THEN** the request is rejected with 401 and no lookup is performed

#### Scenario: A client-supplied identifier in the request is ignored
- **WHEN** a request includes an email or phone value anywhere in its body
  or query string alongside a valid proof token for a different identifier
- **THEN** the system uses only the identifier embedded in the proof token,
  never the client-supplied value

### Requirement: A Non-Identity-Verification Token Is Rejected
The system SHALL reject a token whose `type` claim is not `identity_verified`
(e.g. an access or refresh token) with 401, so a session token issued for an
authenticated staff user can never be replayed against this visitor-facing
endpoint.

#### Scenario: Staff access token rejected
- **WHEN** a caller presents a valid, unexpired staff access token in place
  of an `identity_verified` proof token
- **THEN** the request is rejected with 401 and no lookup is performed

### Requirement: Verified Identifier's Visit History Is Retrievable
The system SHALL return every non-deleted prior visit (invitation or walk-in
registration) whose primary contact email or phone matches the proof token's
verified identifier, within the single tenant this deployment resolves,
ordered most-recent-first. Each entry SHALL include the same fields the
existing public tracking-by-email lookup already exposes for a status
summary (tracking ID and status) plus visit date and purpose, and SHALL NOT
include another visitor's data.

#### Scenario: Matching visits are returned newest first
- **WHEN** a verified identifier has three prior visits on file
- **THEN** the response lists all three, ordered from most recent to oldest

#### Scenario: A visit under a different contact is never returned
- **WHEN** a verified identifier has no prior visits, but a different
  identifier does
- **THEN** the response for the verified identifier includes none of the
  other identifier's visits

### Requirement: No Prior Visit Found Returns an Empty Result, Not an Error
A verified identifier with no matching prior visit SHALL receive a
successful response with an empty visit history and no prefill data, rather
than a 404 or other error — a first-time visitor completing OTP verification
is an expected, valid case, not a failure.

#### Scenario: First-time visitor sees an empty history
- **WHEN** a verified identifier has no prior invitation or registration on
  file
- **THEN** the response is successful, its visit-history list is empty, and
  its prefill payload is absent (null) rather than an error being returned

### Requirement: Prefill Payload Is Drawn From the Most Recent Prior Visit
WHEN a verified identifier has at least one prior visit, the system SHALL
return a prefill payload built from that visitor's most recent prior visit:
full name, email, phone, preferred contact method, ID proof type, ID-proof
document URL (`idProofUrl`), photo URL (`photoUrl`), and visitor category id
(`visitorCategoryId`), when captured. Field names SHALL follow the same
`idProofUrl`/`photoUrl` naming already used for a resolved document/photo URL
elsewhere in this API (e.g. `InvitationVisitorDetailOut`), not any dynamic
form's own field keys — the client rendering this payload has its own fixed
mapping onto the registration form and depends on these exact names
(confirmed by a runtime contract break when an earlier revision used
different names instead). `visitorCategoryId` SHALL be the raw category id
only, following the same id-only convention already used for this field on
every other invitation-facing response (`InvitationOut`,
`InvitationListItemOut`), not a denormalized category name — a client needing
the category's display name resolves it against the existing public
`GET /visitor-categories` listing it already uses to populate its category
picker. The ID-proof document image and photo are the verified identifier's
own previously-submitted files, released under the OTP-proven
`identity_verified` proof token — this is the visitor viewing their own
record, not a staff member viewing someone else's, so
`security-architecture.md` §4's `documents:view` permission (which gates a
*staff* caller's access to someone else's identity document) does not
apply here.

#### Scenario: Prefill uses the most recent visit's contact details
- **WHEN** a verified identifier has two prior visits, an older one under
  the name "J Carter" and a newer one under "John Carter"
- **THEN** the prefill payload's name is "John Carter", drawn from the newer
  visit

#### Scenario: Prefill includes the most recent visit's own ID-proof document
- **WHEN** a verified identifier's most recent prior visit has an ID-proof
  document on file
- **THEN** the prefill payload includes that visit's `idProofType` and a
  fetchable `idProofUrl` for that same document

#### Scenario: Missing photo or ID-proof document is represented as null, not omitted or errored
- **WHEN** the most recent prior visit has no photo, no ID-proof document,
  or neither on file
- **THEN** the prefill payload's `photoUrl`/`idProofUrl` fields are present
  and null for whichever was not captured

#### Scenario: Prefill includes the most recent visit's visitor category
- **WHEN** a verified identifier's most recent prior visit has a
  `visitorCategoryId` set
- **THEN** the prefill payload's `visitorCategoryId` matches that same value

#### Scenario: Missing visitor category is represented as null, not omitted
- **WHEN** the most recent prior visit has no `visitorCategoryId` set
- **THEN** the prefill payload's `visitorCategoryId` field is present and
  null

### Requirement: Lookup Resolves the Same Single Default Tenant as Identity Verification
The returning-visitor lookup SHALL resolve tenant context the same way the
`identity-verification` and `registrations` capabilities already do — a
single server-configured default tenant — since this unauthenticated
endpoint has no other tenant signal available. An unconfigured or inactive
default tenant SHALL be treated as a server-side misconfiguration (logged at
`ERROR`), not a property of the caller's request, consistent with the
equivalent requirement already defined for OTP verification and walk-in
registration.

#### Scenario: Unconfigured default tenant is logged as a server misconfiguration
- **WHEN** a returning-visitor lookup is made and the configured default
  tenant slug does not match any tenant, or matches one that is inactive
- **THEN** the request is rejected and the rejection is logged at `ERROR`,
  distinguishing "no such tenant" from "tenant inactive"

### Requirement: Returning-Visitor Lookup Is Rate-Limited
As a public, unauthenticated endpoint, the returning-visitor lookup SHALL be
rate-limited per the posture `security-architecture.md` §2 requires for
visitor-facing public endpoints, keyed by client IP.

#### Scenario: Requests over the limit are rejected
- **WHEN** a caller exceeds the configured rate limit for the
  returning-visitor lookup endpoint
- **THEN** the system rejects further requests with 429 until the window
  resets

### Requirement: No Visitor Session, User Account, or RBAC Identity Is Created
Successfully retrieving visit history or prefill data SHALL NOT create a
`User` row, issue an access/refresh token pair, or grant any RBAC permission.
The visitor remains unauthenticated in the `auth` capability's sense; the
proof token remains scoped only to this lookup and to submitting a new
registration through the existing, already-unauthenticated
`POST /registrations/walk-in` endpoint.

#### Scenario: No user account is created by a successful lookup
- **WHEN** a returning visitor successfully retrieves their visit history
  and prefill data
- **THEN** no `User` row is created and no access or refresh token is issued
  for that visitor
