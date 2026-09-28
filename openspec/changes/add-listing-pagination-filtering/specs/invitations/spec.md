## ADDED Requirements

### Requirement: Invitation List Supports a Free-Text Search Filter
`GET /invitations` SHALL accept an optional `search` query parameter (max
255 characters) that, when present, narrows results to invitations whose
`primaryContactFullName` OR `trackingId` contains the given value as a
case-insensitive substring match. It SHALL combine with the endpoint's
existing `status`/`registrationType`/`source`/`relevantToMe` filters (`AND`
semantics) and SHALL apply no filter when omitted.

#### Scenario: Searching by contact name
- **WHEN** a caller requests `GET /invitations?search=jane`
- **THEN** only invitations whose `primaryContactFullName` contains "jane"
  (case-insensitive) are returned

#### Scenario: Searching by tracking ID
- **WHEN** a caller requests `GET /invitations?search=<trackingId>` with a
  full or partial tracking ID
- **THEN** only invitations whose `trackingId` contains that value
  (case-insensitive) are returned

#### Scenario: Search combines with other filters
- **WHEN** a caller requests `GET /invitations?search=jane&status=submitted`
- **THEN** only submitted invitations whose contact name or tracking ID
  matches "jane" are returned
