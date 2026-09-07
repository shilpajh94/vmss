## MODIFIED Requirements

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
check-in endpoint — see "Staff Check-In Has One Canonical Endpoint" below.

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

### Requirement: QR Check-In Response Surfaces Full Invitation Detail
A successful QR check-in or check-out response SHALL include everything
captured about the invitation at registration, matching what the public
tracking lookup (`GET /invitations/track?trackingId=`) already returns for
the same invitation, plus the QR-specific fields that lookup doesn't carry:
the visitor's contact details, the resolved host's display name, purpose
of visit and department, registration type and source, the preferred
visit date/time and expected duration, additional notes, carried items,
every co-visitor on a group registration, every declared vehicle, the
submitted/approved/checked-in/checked-out timeline, the invitation's
`expiresAt`, its current `checkInStatus`, and, for the primary contact and
for each visitor who has one on file, their captured profile photo (see
"Visitor and Primary Contact Registration Optionally Captures a Profile
Photo") — null for whichever of them has none. A rejected scan (invalid
token, not approved, watchlist-blocked, expired, or in a status the
attempted action doesn't allow — see the QR check-in and check-out
endpoint requirements below) discloses none of this — only a generic
failure message.

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

### Requirement: Caller Lists Invitations Relevant to Themselves via relevantToMe
`GET /invitations` SHALL accept a `relevantToMe` boolean query parameter.
WHEN `relevantToMe` is true, the system SHALL return invitations where the
authenticated caller is any of:
(a) the user identified by that invitation's `stepOrder` 0 host-identified
`InvitationApprovalStep` (i.e. the snapshotted host) — regardless of that
step's or the invitation's current status;
(b) the delegate assigned to any of that invitation's approval steps (see
the `approvals` capability's "Current Step's Authorized Approver Delegates
It to a Specific Person") — regardless of that step's or the invitation's
current status; or
(c) currently authorized, via branch-scoped role assignment at the
invitation's branch or company-wide, to act on the invitation's current
pending `InvitationApprovalStep` because that step is role-identified and
names a role the caller holds, and no delegate has yet been assigned to
that step — i.e., the caller is one of the role-holders who could act on
the currently-pending step right now, per the `approvals` capability's
role-match authorization rule.
Clause (c) only ever matches while the invitation is `submitted` with an
un-delegated, role-identified step currently pending; once that step is
delegated, acted on, or the invitation leaves `submitted`, a caller who
only ever qualified under (c) (never under (a) or (b)) no longer sees that
invitation via `relevantToMe`. This filter SHALL NOT require the caller to
hold `invitations:view`, and SHALL NOT be scoped by `X-Branch-ID` or the
caller's authorized branches: it is a personal worklist keyed to the
caller's own identity and current approval authority, not the branch-scoped
admin listing the "Employee Lists Invitations at Their Authorized Branches"
requirement above describes. `relevantToMe` SHALL compose with the existing
`status`, `registrationType`, and `source` filters and with
pagination/sorting. A caller matching none of (a)/(b)/(c) for any invitation
SHALL receive an empty, successfully-paginated result, not an error.

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

#### Scenario: A role-holder sees an invitation whose current step needs their role
- **WHEN** a user who holds, via `UserBranchRole` at an invitation's branch,
  the `approverRoleId` role of that invitation's current pending
  role-identified step (and that step has no delegate assigned) requests
  `GET /invitations` with `relevantToMe=true`
- **THEN** the response includes that invitation, even though the user is
  neither the invitation's host nor a delegate — this closes the gap where
  such a user could only find the invitation via the branch-wide list

#### Scenario: A role-holder no longer sees the invitation once someone else's delegation is assigned
- **WHEN** an invitation's current pending step (role-identified, matching a
  role the caller holds) is delegated to a different, specific user
- **THEN** the caller — who is not that delegate — no longer sees the
  invitation via `relevantToMe=true`, since clause (c) requires no delegate
  be assigned

#### Scenario: A role-holder who is not currently authorized on the pending step sees nothing for it
- **WHEN** a user holds a role that does not match the invitation's current
  pending step's `approverRoleId` (e.g. the pending step is for a different
  role, or the invitation is not currently `submitted`)
- **THEN** that invitation is absent from the user's `relevantToMe=true`
  response, unless they separately qualify as its host or a delegate

#### Scenario: Caller who is neither host nor delegate sees nothing for that invitation
- **WHEN** a caller who is not the snapshotted host, has not been delegated
  any step, and does not hold the role of any invitation's current pending
  step requests `GET /invitations` with `relevantToMe=true`
- **THEN** that invitation is absent from the response, even if the caller
  holds `invitations:view` at its branch

#### Scenario: relevantToMe composes with status filtering
- **WHEN** a host requests `GET /invitations` with `relevantToMe=true` and
  `status=submitted`
- **THEN** the response includes only their relevant invitations that are
  currently `submitted`

#### Scenario: No relevant invitations returns an empty page, not an error
- **WHEN** a caller who does not match (a), (b), or (c) for any invitation
  requests `GET /invitations` with `relevantToMe=true`
- **THEN** the response is a successful, empty, correctly-paginated result

#### Scenario: X-Branch-ID is ignored when relevantToMe is set
- **WHEN** a caller requests `GET /invitations` with both `relevantToMe=true`
  and an `X-Branch-ID` header
- **THEN** the response includes the caller's relevant invitations across
  every branch, not narrowed to the named branch

## ADDED Requirements

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

### Requirement: QR Check-In Endpoint Transitions an Eligible Visitor to Checked-In
`PATCH /api/v2/invitations/qr/{token}/check-in` SHALL transition an
invitation whose `checkInStatus` is `unused` or `checked_out` to
`checked_in`, recording `checkedInAt`, subject to the invitation being
`approved`, not watchlist-blocked (unless overridden), and not expired
(`expiresAt` has not already passed). Calling this endpoint for an
invitation whose `checkInStatus` is already `checked_in` SHALL be rejected
with 409 and SHALL NOT change `checkInStatus` — the caller MUST call the
check-out endpoint instead. This endpoint no longer toggles between
check-in and check-out; each action has its own endpoint (see "QR
Check-Out Endpoint Transitions a Checked-In Visitor to Checked-Out").

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

### Requirement: Visitor and Primary Contact Registration Optionally Captures a Profile Photo
The system SHALL accept an optional profile photo file for the primary
contact and for each visitor entry (in both `individual` and `group`
registrations), submitted as an additional file part alongside the
existing ID-proof file(s) in the same `multipart/form-data` request,
order-matched to the visitor list the same way co-visitor ID-proof files
already are. The system SHALL validate the uploaded photo's actual content
against an image-only allow-list (JPEG/PNG) — never the client-supplied
content-type or filename alone — and SHALL enforce a maximum upload size,
consistent with the existing ID-proof validation rules ("Every Visitor Has
a Reachable Contact and a Validated ID Proof"). Omitting the photo for the
primary contact or any visitor SHALL NOT cause the request to be rejected —
the photo remains optional. Because `POST /registrations/walk-in` accepts
the identical payload/file contract as `POST /invitations` (see the
`registrations` capability), this optional photo capture applies to
walk-in registrations without any separate change to that endpoint.

#### Scenario: Photo supplied and valid is stored and returned
- **WHEN** a creation request includes a valid JPEG or PNG photo for the
  primary contact
- **THEN** the request succeeds, the photo is stored, and the invitation's
  detail responses include a URL for it

#### Scenario: Photo omitted does not affect creation
- **WHEN** a creation request supplies no photo for the primary contact or
  any visitor
- **THEN** the request succeeds exactly as it would today, with no photo
  recorded for anyone who didn't supply one

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
  the primary contact and/or one or more visitors
- **THEN** the same validation and storage behavior applies, since it
  submits the identical payload/file contract as `POST /invitations`

## REMOVED Requirements

### Requirement: QR Check-In Drives a Cycling Checked-In/Checked-Out Lifecycle
**Reason**: Replaced by two explicit endpoints — "QR Check-In Endpoint
Transitions an Eligible Visitor to Checked-In" and "QR Check-Out Endpoint
Transitions a Checked-In Visitor to Checked-Out" — so the client (kiosk,
security app) states its intent instead of the server inferring check-in
vs. check-out from the invitation's current state. The underlying
`checkInStatus` tri-state model (`unused`/`checked_in`/`checked_out`) and
its repeatable entry/exit cycling are unchanged; only the single-endpoint
toggle mechanism is removed.
**Migration**: A client that scanned the same QR check-in URL twice in a
row to alternate between checking in and out must instead call the
check-in URL to enter and the new check-out URL to exit. The check-in URL
itself is unchanged for the entry case and now rejects (409) a call made
while already `checked_in`, rather than toggling to checked-out.

### Requirement: QR Check-In Enforces Invitation Expiry on Every Entry
**Reason**: Its content (expiry blocks entry, never blocks exit) is now
stated directly on each of the two explicit endpoints that replace the
toggle — see "QR Check-In Endpoint Transitions an Eligible Visitor to
Checked-In" and "QR Check-Out Endpoint Transitions a Checked-In Visitor to
Checked-Out" — since there is no longer one shared toggle behavior to
describe expiry rules against.
**Migration**: No client-visible change: entry scans are still rejected
past `expires_at` and exit scans still succeed past it, now documented per
endpoint instead of per transition-direction.
