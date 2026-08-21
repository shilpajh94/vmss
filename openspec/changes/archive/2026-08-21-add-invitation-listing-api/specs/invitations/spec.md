## ADDED Requirements

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
primary contact name, purpose of visit, expiry/submission timestamps)
without the per-row visitor/vehicle detail the single-invitation tracking
lookup returns.

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
  status, primary contact name, purpose of visit, and expiry/submission
  timestamps, and does not include the per-visitor or per-vehicle detail
  that `GET /invitations/track` returns for a single invitation
