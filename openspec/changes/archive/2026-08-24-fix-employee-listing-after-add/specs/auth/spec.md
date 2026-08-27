## ADDED Requirements

### Requirement: Single Employee Creation Without a Full Directory Sync

The system SHALL allow a caller holding the `employees:manage` permission to
create one employee directly, setting its `employee_code`, `department_id`,
`phone_number`, and `designation` on creation, without submitting a full
employee directory sync batch.

A single employee created this way SHALL be immediately visible in
`GET /auth/employees` (subject to that endpoint's existing branch-scope and
department-assignment rules), with no follow-up call to the directory sync
endpoint required.

Creating a single employee this way SHALL NOT affect any other existing
employee's `is_active` status — unlike a directory sync batch, it never
deactivates employees omitted from it, since it only ever concerns the one
employee being created.

#### Scenario: Newly created employee appears in the listing right away

- **WHEN** a caller with `employees:manage` creates an employee with a valid
  `department_id` via the single-employee create endpoint
- **THEN** the response returns the created employee with its
  `employee_code`, `department_id`, `phone_number`, and `designation` set
- **AND** a subsequent `GET /auth/employees` call (scoped to that
  employee's branch) includes the new employee without any directory sync
  call in between

#### Scenario: Creating one employee does not deactivate others

- **WHEN** a caller creates a new employee via the single-employee create
  endpoint while other active employees already exist
- **THEN** none of the other existing employees' `is_active` status changes

#### Scenario: Duplicate email is rejected

- **WHEN** a caller attempts to create an employee whose email is already
  registered in the tenant
- **THEN** the system SHALL reject the request with `409 Conflict` and SHALL
  NOT create a new user row

#### Scenario: Referencing a nonexistent department is rejected

- **WHEN** a caller supplies a `department_id` that does not exist in the
  tenant
- **THEN** the system SHALL reject the request with `404 Not Found` and
  SHALL NOT create a new user row

#### Scenario: Caller without permission is denied

- **WHEN** a caller lacking the `employees:manage` permission calls the
  single-employee create endpoint
- **THEN** the system SHALL reject the request with `403 Forbidden` and
  SHALL NOT create a new user row
