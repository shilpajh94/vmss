## MODIFIED Requirements

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

## ADDED Requirements

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
