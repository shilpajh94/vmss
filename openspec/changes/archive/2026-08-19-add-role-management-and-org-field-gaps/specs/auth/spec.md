## MODIFIED Requirements

### Requirement: Role-Based Access Control With Standard and Tenant-Defined Roles
The system SHALL provide exactly five standard roles — Admin, Reception,
Security, Host, and Visitor — seeded into every tenant's schema at
provisioning, and SHALL additionally allow a caller with `roles:manage` to
define any number of additional, tenant-specific custom roles with their own
name, description, and permission set. The system SHALL enforce every
permission check against a caller's actual role grants (standard or custom)
rather than an ad-hoc role-name comparison, and SHALL reject any attempt to
rename or delete one of the five seeded standard roles.

#### Scenario: A freshly provisioned tenant has all five roles
- **WHEN** a new tenant schema finishes provisioning
- **THEN** its `roles` table contains exactly the Admin, Reception,
  Security, Host, and Visitor roles, each with its default permission set

#### Scenario: Permission denial for a caller lacking the permission
- **WHEN** an authenticated caller without the required permission code
  attempts an action gated by `require_permission`/`require_branch_permission`
- **THEN** the request is rejected with 403 and the denial is logged at
  `WARNING`

#### Scenario: A caller with roles:manage creates a custom role
- **WHEN** a caller with `roles:manage` submits a new role name, optional
  description, and a set of permission codes that all exist in the catalog
- **THEN** a new role is created in the tenant's schema with those
  permissions, available for branch-role assignment like any standard role

#### Scenario: Renaming or deleting a standard role is rejected
- **WHEN** a caller attempts to update the name of, or delete, one of the
  five seeded standard roles (Admin, Reception, Security, Host, Visitor)
- **THEN** the request is rejected with a 4xx error and the role is left
  unchanged

#### Scenario: A custom role can be updated and deleted
- **WHEN** a caller with `roles:manage` updates the description or
  permission set of a non-standard (custom) role, or soft-deletes a custom
  role that has no active `UserBranchRole` grants
- **THEN** the update or deletion succeeds

#### Scenario: Deleting a role with active grants is rejected
- **WHEN** a caller attempts to delete a role that at least one
  non-revoked `UserBranchRole` still references
- **THEN** the request is rejected with 409 and the role is left undeleted

### Requirement: Role Name Uniqueness Can Be Verified Before Submission
The system SHALL provide a read-only check for whether a given role name is
already in use (case-insensitive, among non-deleted roles) in the caller's
tenant, so a role-creation or rename form can validate the name before
submitting.

#### Scenario: An available role name is reported as available
- **WHEN** a caller with `roles:view` requests a name-verification check for
  a name no non-deleted role in the tenant currently uses
- **THEN** the response reports the name as available, and no role is
  created or modified as a side effect

#### Scenario: A name already in use is reported as unavailable
- **WHEN** a caller requests a name-verification check for a name a
  non-deleted role (standard or custom) already uses in the same tenant
- **THEN** the response reports the name as unavailable

### Requirement: Role Grants Are Scoped Per Branch/Location
A role grant SHALL apply either to one specific branch or to every branch in
the company (company-wide), and permission checks SHALL honor whichever
scope the grant was made at. A caller with `users:manage` SHALL be able to
revoke a previously granted role assignment.

#### Scenario: Branch-scoped grant restricts access to that branch
- **WHEN** a user holds a role grant scoped to Branch A only
- **THEN** the user's permission checks succeed for requests scoped to Branch
  A and are denied for requests scoped to any other branch

#### Scenario: Company-wide grant applies to every branch
- **WHEN** a user holds a role grant with no branch specified (company-wide)
- **THEN** the user's permission checks succeed for requests scoped to any
  branch in the company

#### Scenario: Revoking a branch-role grant removes access immediately
- **WHEN** a caller with `users:manage` revokes a user's existing branch-role
  assignment
- **THEN** the assignment row no longer exists, and subsequent permission
  checks for that user against that role/branch combination fail

### Requirement: Employee Directory Sync
The system SHALL provide a bulk, authoritative-batch employee-directory sync
endpoint that creates unknown employees, updates known ones, and deactivates
(never deletes) existing employees absent from the batch, validating every
referenced department before writing anything. The employee directory read
endpoint SHALL expose each employee's avatar image (when set) and their
current branch-role assignments, so a caller can render an employee's
identity and access level without a separate lookup per employee.

#### Scenario: Sync batch referencing an unknown department is rejected atomically
- **WHEN** a sync batch includes a `departmentId` that does not exist in the
  tenant's schema
- **THEN** the entire batch is rejected with 404 and no employee in the
  batch is created, updated, or deactivated

#### Scenario: Employee absent from an authoritative batch is deactivated, not deleted
- **WHEN** an existing employee (identified by `employeeCode`) is not present
  in a newly submitted sync batch
- **THEN** that employee's `User` row is deactivated (`is_active = false`),
  never soft-deleted or hard-deleted

#### Scenario: Listing employees includes avatar and role assignments
- **WHEN** a caller with `employees:view` lists employees for a branch
- **THEN** each returned employee includes its avatar URL (null if unset)
  and the list of its current branch-role assignments (role name and
  branch, if any)

## ADDED Requirements

### Requirement: Role Permission Codes Must Exist in the Catalog
The system SHALL reject a role create or update request that references a
permission code not present in the global permission catalog.

#### Scenario: Creating a role with an unknown permission code is rejected
- **WHEN** a caller submits a role create or update request containing a
  permission code that does not exist in the catalog
- **THEN** the request is rejected with 404 and no role is created or
  modified
