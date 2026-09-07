## ADDED Requirements

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
