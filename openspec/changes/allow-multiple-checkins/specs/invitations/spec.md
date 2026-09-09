## ADDED Requirements

### Requirement: Tracking-ID Check-In Endpoint Admits Re-Entry After Check-Out
`PATCH /api/v2/invitations/{trackingId}/check-in` SHALL transition an eligible
invitation from `unused` or `checked_out` `checkInStatus` to `checked_in` —
`checked_out` is not a terminal state for this endpoint, matching the
re-entry rule already in force for the QR check-in endpoint ("QR Check-In
Endpoint Transitions an Eligible Visitor to Checked-In"). An invitation is
eligible only if its `status` shows it was approved at some point (`approved`,
`checked_in`, or `checked_out`) and it is not currently watchlist-flagged.
Calling this endpoint while `checkInStatus` is already `checked_in` SHALL be
rejected with `409` — this endpoint is entry-only; an already-checked-in
visitor exits via the existing check-out endpoints, unaffected by this
requirement. Repeated entry/exit cycles are otherwise unrestricted for the
remainder of the invitation's validity window (`expiresAt`).

#### Scenario: Re-checking in after a check-out succeeds
- **WHEN** a `checked_out` invitation (previously checked in and checked out
  at least once) is submitted to
  `PATCH /api/v2/invitations/{trackingId}/check-in` again
- **THEN** the check-in succeeds — `checkInStatus` and `status` both
  transition to `checked_in`, `checkedInAt` is updated to the current time,
  and the response reflects a successful check-in exactly as it would for a
  first-time check-in

#### Scenario: Multiple check-in/check-out cycles are allowed within one invitation
- **WHEN** an invitation is checked in, checked out, and checked in again two
  or more times before `expiresAt`
- **THEN** every check-in attempt while `checkInStatus` is `unused` or
  `checked_out` succeeds, and every check-out attempt while `checkInStatus`
  is `checked_in` succeeds

#### Scenario: Calling check-in while already checked in is still rejected
- **WHEN** `PATCH /api/v2/invitations/{trackingId}/check-in` is called for an
  invitation whose `checkInStatus` is currently `checked_in`
- **THEN** the system returns `409` and `checkInStatus`/`status` are
  unchanged — the caller must use a check-out endpoint first

#### Scenario: An invitation that was never approved still cannot check in
- **WHEN** `PATCH /api/v2/invitations/{trackingId}/check-in` is called for an
  invitation whose `status` is `submitted` or `denied`
- **THEN** the system returns `409` and no check-in occurs, exactly as before
  this change

#### Scenario: A watchlist-flagged invitation still cannot re-enter
- **WHEN** `PATCH /api/v2/invitations/{trackingId}/check-in` is called for an
  invitation that is currently watchlist-flagged, regardless of whether it
  was previously checked in and checked out
- **THEN** the system returns `409` and no check-in occurs, unchanged from
  the existing watchlist-override gate

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
rejected check-in (invitation not found, never approved, already
`checked_in`, or watchlist-blocked and not overridden) discloses none of
this — only the existing generic failure response. `PATCH
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
- **WHEN** a check-in attempt is rejected (invitation not found, never
  approved, already `checked_in`, or watchlist-blocked and not yet
  overridden)
- **THEN** the response contains only the existing generic failure
  message, with no visitor, host, or visit detail
