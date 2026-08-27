## MODIFIED Requirements

### Requirement: Host Search Validates Query Length and Caps Result Count
`GET /hosts/search` SHALL accept an optional `query`. When `query` is
supplied and non-blank, it SHALL be at least 2 characters, and a shorter
value SHALL be rejected with a validation error. When `query` is omitted
or blank, the endpoint SHALL NOT reject the request and SHALL instead
return a browsable default list of active employees, ordered alphabetically
by name. In both cases the endpoint SHALL accept an optional `limit`
(default 10, maximum 25) capping the number of returned results, using the
same `id`/`name`/`email`/`department` response shape either way.

#### Scenario: Query below minimum length rejected
- **WHEN** a caller requests `GET /hosts/search?query=j`
- **THEN** the request is rejected with a validation error and no search is
  executed

#### Scenario: Omitted query returns a browsable default list
- **WHEN** a caller requests `GET /hosts/search` with no `query` param
- **THEN** the response is `200` with up to `limit` active employees,
  ordered alphabetically by name, in the same shape a matched search
  returns

#### Scenario: Blank query returns a browsable default list
- **WHEN** a caller requests `GET /hosts/search?query=`
- **THEN** the request is treated the same as an omitted query, not
  rejected as below the minimum length

#### Scenario: Result count capped at the requested limit
- **WHEN** more matching (or, for an omitted query, more active) employees
  exist than the requested `limit`
- **THEN** the response returns exactly `limit` results, not the full
  match/employee set
