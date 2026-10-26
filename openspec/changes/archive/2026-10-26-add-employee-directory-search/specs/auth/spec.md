## ADDED Requirements

### Requirement: Employee Directory Free-Text Search

`GET /auth/employees` SHALL accept an optional `search` query parameter of at
most 255 characters. When supplied and non-blank after trimming, the listing
SHALL return only employees whose full name, email, or employee code contains the
term, matched case-insensitively. The match SHALL be a literal substring match:
`%` and `_` in the term SHALL NOT act as wildcards.

`search` SHALL combine with every other supported filter (`departmentId`,
`email`, `role`, `status`), the branch scope, sorting, and pagination. The
pagination metadata (`total`, `totalPages`) SHALL describe the searched result
set, and no employee SHALL appear more than once.

A blank or whitespace-only `search` SHALL behave as if it were not supplied. A
`search` longer than 255 characters SHALL be rejected with a validation error.

#### Scenario: Search by partial name

- **WHEN** a caller requests `GET /auth/employees?search=dina`
- **THEN** the response contains only employees whose name, email, or employee
  code contains "dina" in any letter case
- **AND** `pagination.total` equals the number of matching employees

#### Scenario: Search by employee code

- **WHEN** a caller requests `GET /auth/employees?search=EMP-00` and employees
  with codes `EMP-0012` and `EMP-0034` exist
- **THEN** both employees are returned

#### Scenario: Search combines with an existing filter

- **WHEN** a caller requests `GET /auth/employees?search=dina&status=active`
- **THEN** only active employees matching "dina" are returned

#### Scenario: Wildcard characters are literal

- **WHEN** a caller requests `GET /auth/employees?search=%25`
- **THEN** only employees whose name, email, or code literally contains `%` are
  returned, not every employee

#### Scenario: Blank search is ignored

- **WHEN** a caller requests `GET /auth/employees?search=%20%20`
- **THEN** the response is identical to a request with no `search`

#### Scenario: Search respects branch scope

- **WHEN** a caller supplies `X-Branch-ID` and a `search` term matching an
  employee tied only to a different branch
- **THEN** that employee is not returned

#### Scenario: Overlong search is rejected

- **WHEN** a caller supplies a `search` of 256 characters
- **THEN** the request fails validation with a 4xx error envelope
