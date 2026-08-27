## MODIFIED Requirements

### Requirement: Employee Directory Sync
The system SHALL provide a bulk, authoritative-batch employee-directory sync
endpoint that creates unknown employees, updates known ones, and deactivates
(never deletes) existing employees absent from the batch, validating every
referenced department before writing anything. The employee directory read
endpoint SHALL expose each employee's avatar image (when set) and their
current branch-role assignments, so a caller can render an employee's
identity and access level without a separate lookup per employee.

Listing employees (`GET /auth/employees`) SHALL require no bearer token and
no permission check. When the request carries a valid access token, the
endpoint SHALL resolve the tenant from that token's `tenant_id` claim, the
same tenant an authenticated request would resolve to; when no token is
presented, or the presented token does not resolve to a real, active tenant,
the endpoint SHALL instead resolve the deployment's configured default
tenant. `X-Branch-ID` SHALL remain optional: when supplied, results are
scoped to that one branch; when omitted, results include every branch in
the resolved tenant, with no notion of a caller's authorized branches (since
there is no caller).

Listing employees SHALL additionally accept two optional filters, composable
with each other, with `departmentId`, and with pagination/sorting:
- `email` — exact match against the employee's email address.
- `role` — matches employees holding that role name via any of their
  branch-role assignments (a role held at any branch in scope qualifies,
  not only a role held at the branch named by `X-Branch-ID`).

Listing employees SHALL remain rate-limited by client IP, consistent with
the posture `security-architecture.md` §2 requires for every unauthenticated
endpoint.

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
- **WHEN** a caller lists employees for a branch
- **THEN** each returned employee includes its avatar URL (null if unset)
  and the list of its current branch-role assignments (role name and
  branch, if any)

#### Scenario: Listing employees without a branch header returns every authorized branch's employees
- **WHEN** a request sends `GET /auth/employees` with no `X-Branch-ID` header
- **THEN** the response includes employees from every branch in the resolved
  tenant — there is no longer a notion of a caller's authorized branches to
  narrow this further, since the endpoint requires no caller

#### Scenario: Listing employees requires no bearer token
- **WHEN** a request sends `GET /auth/employees` with no `Authorization`
  header
- **THEN** the request is not rejected for missing credentials, and the
  employee list is returned scoped to the deployment's configured default
  tenant

#### Scenario: A presented token still resolves the caller's own tenant
- **WHEN** a request sends `GET /auth/employees` with a valid access token
  whose `tenant_id` claim resolves to a real, active tenant other than the
  configured default tenant
- **THEN** the response lists that token's tenant's employees, not the
  default tenant's

#### Scenario: Filtering employees by email returns an exact match
- **WHEN** a request sends `GET /auth/employees?email=jane@example.com`
- **THEN** the response includes only the employee whose email is exactly
  `jane@example.com`, if one exists in scope

#### Scenario: Filtering employees by role returns employees holding that role anywhere in scope
- **WHEN** a request sends `GET /auth/employees?role=Receptionist`
- **THEN** the response includes every employee in scope who holds a
  branch-role assignment with role name `Receptionist` at any branch,
  without duplicate entries for an employee holding that role at more than
  one branch

#### Scenario: Listing employees is rate-limited by client IP
- **WHEN** one client IP sends more than 60 `GET /auth/employees` requests
  within a minute
- **THEN** the excess requests are rejected with 429, the same as any other
  unauthenticated endpoint

### Requirement: Reception Desk and Security Gate CRUD
The system SHALL provide full CRUD for `ReceptionDesk` (scoped to one
`Floor`) and `SecurityGate` (scoped to one `Branch`, optionally narrowed to
one `Building`), with the same branch-authorization and cross-branch 404
behavior as Building/Floor/Department for every get-by-id/update/delete
request. Each `ReceptionDesk` SHALL carry a three-state operational status
(`active`, `maintenance`, `inactive`) in place of a plain active/inactive
flag. Each `SecurityGate` SHALL carry its entry/exit/both gate type and MAY
be flagged as a high-security gate; it SHALL NOT carry a connectivity-status
field or an authentication-method field. `X-Branch-ID` SHALL be optional on
every ReceptionDesk/SecurityGate endpoint. Listing `ReceptionDesk`/
`SecurityGate` is public (see "Master-Data Listing Endpoints Are Public"
below); get/update/delete-by-id endpoints continue to resolve authorization
from the target resource's own branch, creating a `SecurityGate` resolves
the branch from the body's `branchId`, and creating a `ReceptionDesk`
resolves it transitively from the body's `floorId`.

#### Scenario: Security gate optionally narrowed to a building
- **WHEN** a `SecurityGate` is created with a `buildingId` that does not
  belong to the gate's `branchId`
- **THEN** the request is rejected with 404

#### Scenario: A reception desk can be set to maintenance status
- **WHEN** a caller with `desks:manage` updates a `ReceptionDesk`'s `status`
  to `maintenance`
- **THEN** the desk's status is stored as `maintenance`, distinct from both
  `active` and `inactive`

#### Scenario: A security gate's connectivity status is independent of its gate type
- **WHEN** a caller with `gates:manage` sends `POST /security-gates` or
  `PUT /security-gates/{id}` with `gateType: both` and, in the same request
  body, a `connectivityStatus` or `authMethod` field
- **THEN** the gate is created/updated with that `gateType`, and the
  `connectivityStatus`/`authMethod` values are ignored — the gate no longer
  carries a connectivity-status or auth-method field at all, so nothing
  about its gate type can be constrained by or independent of them

#### Scenario: Creating a security gate resolves its branch from the body without requiring a header
- **WHEN** a caller with `gates:manage` sends `POST /security-gates` with
  `branchId` in the body and no `X-Branch-ID` header
- **THEN** the gate is created under that branch, provided the caller holds
  `gates:manage` there; otherwise 403, or 404 if the branch does not exist
  or is inactive

#### Scenario: Creating a reception desk resolves its branch transitively from floorId
- **WHEN** a caller with `desks:manage` sends `POST /reception-desks` with
  `floorId` in the body and no `X-Branch-ID` header
- **THEN** the system resolves the desk's branch via the named floor's
  building and creates the desk, provided the caller holds `desks:manage` at
  that branch; otherwise the request is rejected with 403, or 404 if the
  floor does not exist
