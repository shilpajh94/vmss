## MODIFIED Requirements

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
