## ADDED Requirements

### Requirement: Admin Can Disable and Re-Enable a Single Employee

The system SHALL allow a caller holding `employees:manage` to disable an
employee (`POST /auth/employees/{id}/disable`) and to re-enable a disabled
employee (`POST /auth/employees/{id}/enable`). Disabling is reversible and
SHALL NOT remove any data.

A disabled employee SHALL be unable to log in, SHALL NOT be accepted as a
`hostId` on new invitations/walk-ins, SHALL NOT appear in host search, and
SHALL appear in `GET /auth/employees` only under `status=inactive`. Existing
access tokens held by the employee SHALL stop working once disabled. Both
operations SHALL be idempotent and SHALL be recorded in the audit trail.

#### Scenario: Disabled employee cannot sign in

- **WHEN** an admin disables an employee and that employee then submits valid credentials
- **THEN** login is rejected with `401` and the same generic message used for any invalid login

#### Scenario: Disabled employee's existing session is revoked

- **WHEN** an admin disables an employee who holds an unexpired access token
- **THEN** the next authenticated request using that token is rejected with `401`

#### Scenario: Disabled employee is excluded from host selection

- **WHEN** an admin disables an employee
- **THEN** host search no longer returns that employee
- **AND** creating an invitation with that employee as `hostId` is rejected

#### Scenario: Re-enabling restores access

- **WHEN** an admin re-enables a previously disabled employee
- **THEN** the employee can log in again and appears under `status=active`

#### Scenario: Repeated disable is a no-op

- **WHEN** an admin disables an employee who is already disabled
- **THEN** the request succeeds without error and no second audit entry is written

#### Scenario: Caller without permission is denied

- **WHEN** a caller lacking `employees:manage` calls the disable or enable endpoint
- **THEN** the system SHALL reject the request with `403 Forbidden` and change nothing

#### Scenario: Unknown employee

- **WHEN** the employee id does not exist in the caller's tenant
- **THEN** the system SHALL respond `404 Not Found`

### Requirement: Admin Can Delete a Single Employee

The system SHALL allow a caller holding `employees:manage` to delete an
employee (`DELETE /auth/employees/{id}`). Deletion SHALL be a soft delete: the
record is retained for audit and for historical invitations that reference the
employee, but the employee SHALL disappear from every employee listing and
lookup, SHALL be unable to authenticate, and SHALL have their email and
employee code released so they can be reused by a new employee.

Deleting SHALL be recorded in the audit trail and SHALL be idempotent in effect
(a second delete returns `404`).

#### Scenario: Deleted employee disappears from listings

- **WHEN** an admin deletes an employee
- **THEN** `GET /auth/employees` (any `status` filter) and host search no longer return them

#### Scenario: Historical invitations still resolve

- **WHEN** an employee who hosted past invitations is deleted
- **THEN** those invitations remain readable and continue to display the host's name

#### Scenario: Email and employee code can be reused

- **WHEN** an employee is deleted and a new employee is created with the same email and employee code
- **THEN** creation succeeds

#### Scenario: Deleted employee cannot sign in

- **WHEN** a deleted employee submits their old credentials
- **THEN** login is rejected with the same generic `401`

#### Scenario: Caller without permission is denied

- **WHEN** a caller lacking `employees:manage` calls the delete endpoint
- **THEN** the system SHALL reject with `403 Forbidden` and delete nothing

### Requirement: Employee Disable and Delete Protect Admin Access

The system SHALL reject disabling or deleting the calling admin's own account,
and SHALL reject disabling or deleting an employee if that would leave the
tenant with no active user holding an administrative role. Rejections SHALL use
`409 Conflict` with a message that does not reveal other users' details.

#### Scenario: Admin cannot disable themself

- **WHEN** an admin calls disable or delete on their own user id
- **THEN** the system SHALL respond `409 Conflict` and change nothing

#### Scenario: Last active admin cannot be removed

- **WHEN** an admin tries to disable or delete the only remaining active admin
- **THEN** the system SHALL respond `409 Conflict` and change nothing

### Requirement: Directory Sync Does Not Re-Enable Admin-Disabled Employees

An employee disabled through the admin disable endpoint SHALL remain disabled
when a subsequent directory sync batch includes them. Sync SHALL continue to
update their directory fields, but SHALL NOT set them active. Employees that
sync itself deactivated (by omission from a batch) SHALL continue to be
re-activated when they reappear in a later batch. An employee deleted through
the admin delete endpoint SHALL be treated as non-existent by sync, so a batch
containing their email creates a new employee.

#### Scenario: Sync leaves a manually disabled employee disabled

- **WHEN** an admin disables an employee and a later sync batch includes that employee
- **THEN** the employee's directory fields are updated and they remain disabled

#### Scenario: Sync-deactivated employee returns on reappearance

- **WHEN** an employee was deactivated only because a prior batch omitted them and a later batch includes them
- **THEN** they become active again
