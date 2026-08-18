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
The system SHALL resolve which branch/location an authenticated request
operates against from an explicit per-request signal (not a static JWT
claim), and SHALL reject the request if the caller has no role grant at that
branch or company-wide.

#### Scenario: Caller with a grant at the requested branch succeeds
- **WHEN** an authenticated request includes `X-Branch-ID` naming a branch the
  caller holds a role grant at (branch-specific or company-wide)
- **THEN** the request proceeds and subsequent log lines for that request
  carry the resolved `branch_id`

#### Scenario: Caller with no grant at the requested branch is rejected
- **WHEN** an authenticated request includes `X-Branch-ID` naming a branch the
  caller holds no role grant at, branch-specific or company-wide
- **THEN** the request is rejected with 403

### Requirement: Role-Based Access Control With Five Standard Roles
The system SHALL provide exactly five standard roles — Admin, Reception,
Security, Host, and Visitor — seeded into every tenant's schema at
provisioning, and SHALL enforce every permission check against a caller's
actual role grants rather than an ad-hoc role-name comparison.

#### Scenario: A freshly provisioned tenant has all five roles
- **WHEN** a new tenant schema finishes provisioning
- **THEN** its `roles` table contains exactly the Admin, Reception, Security,
  Host, and Visitor roles, each with its default permission set

#### Scenario: Permission denial for a caller lacking the permission
- **WHEN** an authenticated caller without the required permission code
  attempts an action gated by `require_permission`/`require_branch_permission`
- **THEN** the request is rejected with 403 and the denial is logged at
  `WARNING`

### Requirement: Role Grants Are Scoped Per Branch/Location
A role grant SHALL apply either to one specific branch or to every branch in
the company (company-wide), and permission checks SHALL honor whichever
scope the grant was made at.

#### Scenario: Branch-scoped grant restricts access to that branch
- **WHEN** a user holds a role grant scoped to Branch A only
- **THEN** the user's permission checks succeed for requests scoped to Branch
  A and are denied for requests scoped to any other branch

#### Scenario: Company-wide grant applies to every branch
- **WHEN** a user holds a role grant with no branch specified (company-wide)
- **THEN** the user's permission checks succeed for requests scoped to any
  branch in the company

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
