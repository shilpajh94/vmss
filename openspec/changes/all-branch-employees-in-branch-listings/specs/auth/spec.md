## ADDED Requirements

### Requirement: Branch-Scoped Employee Listing Includes All-Branch Employees

When `GET /auth/employees` is scoped to one branch (via `X-Branch-ID`), the
system SHALL return every non-deleted employee who either **belongs to that
branch** or **belongs to all branches**. An employee belongs to a branch if
their department is at that branch or they hold a role grant scoped to that
branch. An employee belongs to all branches if they hold a company-wide role
grant, or have no department and no branch-scoped role grant.

An all-branch employee SHALL appear in the listing of every branch. An
employee SHALL appear at most once per result and be counted once in the
pagination total, regardless of how many roles or grants they hold. Employees
who belong only to other branches SHALL NOT be returned. The unscoped listing
(no `X-Branch-ID`) SHALL be unchanged.

#### Scenario: All-branch employee appears under any branch

- **WHEN** an employee with no department and no branch-scoped role grant exists
- **AND** the listing is requested with `X-Branch-ID` of branch A, then of branch B
- **THEN** the employee is returned in both responses

#### Scenario: Branch employees and all-branch employees are combined

- **WHEN** branch A has employee X, branch B has employee Y, and employee Z is all-branch
- **AND** the listing is requested scoped to branch A
- **THEN** X and Z are returned and Y is not

#### Scenario: Multi-role employee is not duplicated

- **WHEN** an employee holds one role at branch A, another role at branch B, and a company-wide role
- **AND** the listing is requested scoped to branch A
- **THEN** the employee appears exactly once and `total` counts them once

#### Scenario: Role filter includes all-branch holders

- **WHEN** an all-branch employee holds the `host` role company-wide
- **AND** the listing is requested with `role=host` and `X-Branch-ID` of any branch
- **THEN** the employee is returned, so the approval delegate picker offers them

#### Scenario: Disable/delete reachable from any branch

- **WHEN** an admin views the listing scoped to a branch the all-branch employee is not assigned to
- **THEN** the employee is listed with the same data as elsewhere, and disable, enable, and delete (`employees:manage`) work on them

#### Scenario: Unscoped listing unchanged

- **WHEN** the listing is requested without `X-Branch-ID`
- **THEN** every non-deleted employee is returned as before
