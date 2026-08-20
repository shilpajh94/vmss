# auth Specification

## Purpose

Baseline requirements for the `auth` capability — JWT issuance,
tenant/branch-context resolution, and branch-scoped RBAC — including the two
traceability clarifications a compliance re-audit of API-01 and API-02
surfaced, so they're verifiable requirements rather than implicit knowledge
held only in design notes.

## Requirements

### Requirement: JWT-Based Authentication
The system SHALL authenticate users via short-lived JWT access tokens and
longer-lived refresh tokens, issued only after password verification against
an Argon2 hash, and SHALL reject any token that is expired, malformed, or
signed with the wrong key.

#### Scenario: Successful login issues a token pair
- **WHEN** a caller submits valid email/password credentials to
  `POST /auth/login`
- **THEN** the response includes an access token and a refresh token, and the
  access token's claims include the caller's `tenant_id`

#### Scenario: Expired or invalid token is rejected
- **WHEN** a request presents an expired, tampered, or wrong-type (e.g. a
  refresh token used where an access token is required) bearer token
- **THEN** the request is rejected with 401 and no tenant/user resolution is
  attempted

### Requirement: Tenant Identity Is Carried From Day One for Multi-Tenant Readiness
Every access token SHALL carry a `tenant_id` claim identifying the caller's
company/account, and every authenticated request SHALL resolve that claim to
exactly one tenant before any tenant-scoped data is read or written. This
`tenant_id` is the field that satisfies "carry company_id from day one for
future multi-tenant readiness" — under this system's schema-per-tenant
design, one Postgres schema is one company account, so `tenant_id` and the
requirement's "company_id" are the same concept under a different name. The
tenant's own business-profile row (`Company`, `org_structure` capability) is
a separate concept — a single, non-request-scoped record describing *this*
company's identity (legal name, logo, contact info) — and is NOT carried in
JWT claims or bound into per-request logging context, because exactly one
`Company` row is enforced per tenant schema and there is no second candidate
for a per-request identifier to disambiguate.

#### Scenario: Tenant resolves before any tenant-scoped query runs
- **WHEN** an access token's `tenant_id` claim is decoded
- **THEN** the system looks up that id in the global tenant registry, and
  only proceeds to load tenant-scoped data (including the current user) once
  the tenant is found and active

#### Scenario: Unknown or inactive tenant is rejected
- **WHEN** an access token's `tenant_id` claim does not match any tenant, or
  matches a tenant flagged inactive
- **THEN** the request is rejected with 401 before any tenant-schema query is
  attempted

### Requirement: Branch/Location-Scoped Access Context
The system SHALL let a request identify which branch/location it operates
against via an `X-Branch-ID` header, but SHALL NOT require that header on
every branch-scoped request. When `X-Branch-ID` is supplied, the system
SHALL reject the request with 403 if the caller has no role grant at that
branch (branch-specific or company-wide). When it is omitted:
- On a request that lists branch-scoped resources, the system SHALL scope
  the result to every branch the caller holds a grant covering the relevant
  permission at — every branch, if the caller holds that permission
  company-wide.
- On a request that reads, updates, or deletes one branch-scoped resource by
  id, the system SHALL resolve the resource's actual branch by looking it
  up, and authorize the caller against that branch.
- On a request that creates a branch-scoped resource, the system SHALL
  resolve the branch from a branch-identifying field already present in the
  request body (directly or transitively), where one exists.
- A caller holding no grant at all for the relevant permission, at any
  branch, SHALL be rejected with 403 regardless of whether `X-Branch-ID` was
  supplied.

#### Scenario: Caller with a grant at the requested branch succeeds
- **WHEN** an authenticated request includes `X-Branch-ID` naming a branch the
  caller holds a role grant at (branch-specific or company-wide)
- **THEN** the request proceeds and subsequent log lines for that request
  carry the resolved `branch_id`

#### Scenario: Caller with no grant at the requested branch is rejected
- **WHEN** an authenticated request includes `X-Branch-ID` naming a branch the
  caller holds no role grant at, branch-specific or company-wide
- **THEN** the request is rejected with 403

#### Scenario: Omitting the header on a list request scopes to every authorized branch
- **WHEN** an authenticated caller sends a list request for a branch-scoped
  resource with no `X-Branch-ID` header, and holds the relevant view
  permission company-wide
- **THEN** the response includes matching rows from every branch, not just
  one

#### Scenario: Omitting the header on a list request scopes to the caller's specific branches
- **WHEN** an authenticated caller sends a list request for a branch-scoped
  resource with no `X-Branch-ID` header, and holds the relevant view
  permission only at specific branches (not company-wide)
- **THEN** the response includes matching rows from only those branches

#### Scenario: Omitting the header on a by-id request resolves branch from the entity
- **WHEN** an authenticated caller sends a GET, PUT, PATCH, or DELETE
  request for one branch-scoped resource by id, with no `X-Branch-ID` header
- **THEN** the system authorizes the caller against the resource's actual
  branch, succeeding if the caller holds the relevant permission there
  (branch-specific or company-wide) and rejecting with 404 otherwise —
  indistinguishable from the resource not existing

#### Scenario: A caller with no grant anywhere is rejected regardless of the header
- **WHEN** an authenticated caller holds no role grant carrying the relevant
  permission at any branch, company-wide or otherwise
- **THEN** every request gated by that permission is rejected with 403,
  whether or not `X-Branch-ID` was supplied

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
- **THEN** its `roles` table contains exactly the Admin, Reception, Security,
  Host, and Visitor roles, each with its default permission set

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

### Requirement: Role Permission Codes Must Exist in the Catalog
The system SHALL reject a role create or update request that references a
permission code not present in the global permission catalog, and SHALL
provide a read-only endpoint for a caller with `roles:view` to retrieve the
full list of valid permission codes for their tenant, so a role-creation or
role-update form can be populated with codes known to be valid before
submission.

#### Scenario: Creating a role with an unknown permission code is rejected
- **WHEN** a caller submits a role create or update request containing a
  permission code that does not exist in the catalog
- **THEN** the request is rejected with 404 and no role is created or
  modified

#### Scenario: Permission catalog is retrievable
- **WHEN** a caller with `roles:view` requests the permission catalog
- **THEN** the response lists every permission code the tenant's roles can be
  granted, in a form a client can use directly as the choices for a
  role-creation or role-update form's permission-code field

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

### Requirement: The Visitor Role Grants No Access and Is Never Assignable to a User
The "Visitor" role SHALL exist in the seeded role catalog (to satisfy the
five-role requirement) but SHALL carry zero permissions, and the system
SHALL reject any attempt to grant it to a `User` account — because visitors
do not authenticate through this JWT/RBAC system at all; they are handled by
separate, unauthenticated, signed-token flows.

#### Scenario: Visitor role carries no permissions
- **WHEN** the seeded role catalog is inspected for any tenant
- **THEN** the "Visitor" role's permission set is empty

#### Scenario: Assigning the Visitor role to a user is rejected
- **WHEN** a caller with `users:manage` attempts to grant the "Visitor" role
  to a `User` via the branch-role assignment endpoint
- **THEN** the request is rejected with a 4xx error and no `UserBranchRole`
  row is created
