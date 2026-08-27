# Visit Info Lookup Specification

## Purpose

Serves the unauthenticated walk-in registration wizard's "Visit Info" step
with real backend-driven host search, department listing, and purpose/
duration options, replacing the app's hardcoded lists and free-text-only
Host/Department inputs.

## Requirements

### Requirement: Host Search Returns Active Employees Matching Name or Email
`GET /hosts/search` SHALL return active employees whose name or email
contains the supplied `query`, matched case-insensitively, each with `id`,
`name`, `email`, and `department` (the employee's current department name,
omitted/null if the employee has none set). Deactivated employees SHALL NOT
appear in results.

#### Scenario: Partial name match
- **WHEN** a caller requests `GET /hosts/search?query=john` and an active
  employee named "John Carter" exists
- **THEN** the response includes that employee's `id`, `name`, `email`, and
  `department` (if set)

#### Scenario: Deactivated employee excluded
- **WHEN** an employee matching the query has been deactivated via employee
  directory sync
- **THEN** that employee does not appear in the search results

#### Scenario: No match returns an empty list, not a 404
- **WHEN** no active employee's name or email contains the supplied query
- **THEN** the response is `200` with an empty `hosts` array

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

### Requirement: Department Listing Is Scoped to the Kiosk's Resolved Branch
`GET /visit-info/departments` SHALL return only active, non-deleted
departments belonging to the branch resolved from the caller's device
credential (the same resolution `POST /registrations/walk-in` uses), each
with `id` and `name`.

#### Scenario: Departments from other branches are not returned
- **WHEN** a request's resolved branch has departments, and other branches
  also have departments
- **THEN** the response includes only the resolved branch's departments

#### Scenario: Inactive or deleted department excluded
- **WHEN** a department has been deactivated or soft-deleted
- **THEN** it does not appear in the response

### Requirement: Visit Purpose and Duration Options Are Served From Configured Catalogs
`GET /visit-info/options` SHALL return every active visit purpose and every
active visit duration configured for the tenant, each as `{id, name}`, with
each duration additionally carrying a `minutes` integer. Results SHALL be
ordered by their configured display order.

#### Scenario: Options response includes both lists together
- **WHEN** a caller requests `GET /visit-info/options`
- **THEN** the response includes a `purposes` array and a `durations` array,
  each populated from the tenant's configured catalogs rather than a
  hardcoded list

#### Scenario: Duration carries a machine-usable minute value
- **WHEN** the response includes a duration named "Half day (4 hours)"
- **THEN** that entry's `minutes` field is `240`

### Requirement: Lookup Endpoints Resolve Tenant and Branch From a Device Credential, Never From the Request
All three lookup endpoints SHALL resolve tenant (and, for department
listing, branch) using the same device-credential resolution
`POST /registrations/walk-in` uses, including its default-tenant/branch
fallback when no credential is presented. No tenant or branch identifier in
the query string or request body SHALL ever be trusted.

#### Scenario: Client-supplied tenant/branch values are ignored
- **WHEN** a request to any of the three endpoints includes a tenant or
  branch identifier as a query parameter
- **THEN** the system ignores it and resolves tenant/branch solely from the
  device credential (or its fallback)

### Requirement: Lookup Endpoints Are Rate-Limited
Each of the three lookup endpoints SHALL be rate-limited per caller IP,
consistent with the posture applied to other public lookup endpoints.

#### Scenario: Requests over the limit are rejected
- **WHEN** a caller exceeds the configured rate limit on any of the three
  endpoints
- **THEN** further requests are rejected with 429 until the window resets
