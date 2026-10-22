## ADDED Requirements

### Requirement: Invitation List Supports a Purpose-of-Visit Filter
`GET /invitations` SHALL accept an optional `purposeOfVisit` query parameter
(max 255 characters) that, when present, narrows results to invitations
whose purpose of visit is exactly equal to the given value. It SHALL combine
with the endpoint's existing `status`/`registrationType`/`source`/`search`/
`relevantToMe` filters (`AND` semantics), the response's `pagination.total`
SHALL count only matching invitations, and it SHALL apply no filter when
omitted.

#### Scenario: Filtering by purpose of visit
- **WHEN** a caller requests `GET /invitations?purposeOfVisit=Interview`
- **THEN** only invitations whose purpose of visit is exactly "Interview"
  are returned, and `pagination.total` equals the number of such invitations

#### Scenario: Purpose filter combines with status
- **WHEN** a caller requests
  `GET /invitations?purposeOfVisit=Interview&status=submitted`
- **THEN** only submitted invitations whose purpose of visit is
  "Interview" are returned

#### Scenario: Purpose filter applies in relevantToMe mode
- **WHEN** a caller requests
  `GET /invitations?relevantToMe=true&purposeOfVisit=Delivery`
- **THEN** only invitations on the caller's personal worklist whose
  purpose of visit is "Delivery" are returned

#### Scenario: Partial value does not match
- **WHEN** a caller requests `GET /invitations?purposeOfVisit=Inter`
- **THEN** an invitation whose purpose of visit is "Interview" is not
  returned

#### Scenario: Over-long value rejected
- **WHEN** a caller requests `GET /invitations` with a `purposeOfVisit`
  value longer than 255 characters
- **THEN** the system rejects the request with a validation error
