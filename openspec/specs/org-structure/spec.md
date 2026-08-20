# org-structure Specification

## Purpose

Baseline requirements for the `org-structure` capability — CRUD over the
Company → Branch → Building → Floor → Department org chart plus Reception
Desk/Security Gate and employee-directory sync — including the two fixes a
compliance re-audit of API-03 and API-04 surfaced: soft-deleted rows must
free their unique code/number for reuse, and `Company.email` must validate
as a real email address.

## Requirements

### Requirement: Company Is a Tenant-Scoped Singleton
The system SHALL allow exactly one `Company` profile per tenant schema,
rejecting a second creation attempt while an active one exists.

#### Scenario: Creating a second company profile is rejected
- **WHEN** a caller with `companies:manage` attempts to create a `Company`
  profile while one already exists and is not deleted
- **THEN** the request is rejected with 409

#### Scenario: Company profile is company-wide, not branch-scoped
- **WHEN** any Company CRUD endpoint is called
- **THEN** it requires only a company-wide permission (`companies:manage`/
  `companies:view`), never an `X-Branch-ID` header

### Requirement: Company Profile Carries Default Visitor Policy Settings
The `Company` profile SHALL store this tenant's default timezone, whether
pre-registered visitors are auto-approved by default, and the default badge
expiry duration, as tenant-wide configuration available to every branch
unless overridden elsewhere.

#### Scenario: Organisation-wide defaults are set on the company profile
- **WHEN** a caller with `companies:manage` updates the `Company` profile
  with a `defaultTimezone`, `autoApprovePreRegisteredVisitors` flag, and
  `badgeExpiryDurationMinutes`
- **THEN** the values are persisted on the single `Company` row and returned
  on subsequent reads

### Requirement: Branch, Building, Floor, and Department CRUD
The system SHALL provide full CRUD for `Branch` (company-wide) and for
`Building`/`Floor`/`Department` (branch-scoped), rejecting any request whose
target does not actually belong to a branch the caller is authorized for. A
`Department` SHALL be creatable directly under a `Branch`, with an optional
`Floor` association rather than a mandatory one — a department is not
required to be assigned to a specific floor to exist. The system SHALL
additionally provide a bulk provisioning operation that creates a new
`Branch` together with as much of its Building → Floor → Department/
ReceptionDesk chain and SecurityGates as a single request supplies, in one
transaction. `Branch` and `Building` SHALL accept their active/inactive
status at creation time, not only via a later update. `X-Branch-ID` SHALL be
optional on every Building/Floor/Department endpoint: list endpoints scope
to every branch the caller is authorized for when it is omitted; get/update/
delete-by-id endpoints resolve authorization from the target resource's own
branch; creating a `Building`/`Department` resolves the branch from the
body's `branchId`, and creating a `Floor` resolves it transitively from the
body's `buildingId`.

#### Scenario: Branch-scoped entity outside the authorized branch is hidden as 404
- **WHEN** a caller authorized at Branch A requests, updates, or deletes a
  Building/Floor/Department that actually belongs to Branch B (by id, path,
  or list filter)
- **THEN** the request is rejected with 404, not 403 — indistinguishable
  from the target not existing at all

#### Scenario: A single company operates multiple branches
- **WHEN** more than one `Branch` row exists in a tenant's schema
- **THEN** every branch-scoped entity (Building/Floor/Department/
  ReceptionDesk/SecurityGate) correctly resolves to exactly one owning
  branch, and a caller's list/detail views for one branch never include
  another branch's rows

#### Scenario: Bulk provisioning creates a whole org-chart tree in one transaction
- **WHEN** a caller with `branches:provision` submits a single request
  describing a new branch's buildings, floors, departments, reception
  desks, and security gates
- **THEN** every row in the tree is created in one transaction, and the
  response reports counts of each entity type created

#### Scenario: A conflict anywhere in bulk provisioning leaves nothing committed
- **WHEN** a bulk provisioning request fails a uniqueness check — against
  existing data, or against a sibling entity within the same request —
  partway through
- **THEN** the request is rejected with 409 and no row from that request is
  left committed, so a corrected retry starts from a clean slate

#### Scenario: Bulk provisioning requires its own, stricter permission
- **WHEN** a caller holds `branches:manage` (sufficient for plain
  single-branch CRUD) but not `branches:provision`
- **THEN** a bulk provisioning request is rejected with 403

#### Scenario: A department can be created under a branch with no floor
- **WHEN** a caller with `departments:manage` creates a `Department`
  supplying a `branchId` and no `floorId`
- **THEN** the department is created successfully and is listed among that
  branch's departments regardless of any floor assignment

#### Scenario: A branch is created with its operational status set explicitly
- **WHEN** a caller with `branches:manage` creates a `Branch` supplying
  `isActive: false`
- **THEN** the created branch is inactive from creation, with no separate
  update call required

#### Scenario: Listing buildings without a branch header returns every authorized branch's rows
- **WHEN** a caller with `buildings:view` company-wide sends
  `GET /buildings` with no `X-Branch-ID` header
- **THEN** the response includes buildings from every branch in the tenant

#### Scenario: Listing buildings without a branch header, for a branch-restricted caller, is scoped to their branches
- **WHEN** a caller with `buildings:view` granted only at specific branches
  sends `GET /buildings` with no `X-Branch-ID` header
- **THEN** the response includes buildings from only those branches

#### Scenario: Getting a building by id without a branch header resolves from the building itself
- **WHEN** a caller with `buildings:view` at the building's actual branch
  sends `GET /buildings/{id}` with no `X-Branch-ID` header
- **THEN** the building is returned; a caller without `buildings:view` at
  that branch instead receives 404

#### Scenario: Creating a building resolves its branch from the body regardless of the header
- **WHEN** a caller with `buildings:manage` sends `POST /buildings` with
  `branchId` in the body, with or without an `X-Branch-ID` header
- **THEN** the building is created under the body's `branchId`, provided the
  caller holds `buildings:manage` there; otherwise 403, or 404 if that
  branch does not exist or is inactive

#### Scenario: Creating a floor resolves its branch transitively from buildingId
- **WHEN** a caller with `floors:manage` sends `POST /floors` with
  `buildingId` in the body and no `X-Branch-ID` header
- **THEN** the system resolves the floor's branch via the named building and
  creates the floor, provided the caller holds `floors:manage` at that
  branch; otherwise the request is rejected with 403, or 404 if the building
  does not exist

### Requirement: Reception Desk and Security Gate CRUD
The system SHALL provide full CRUD for `ReceptionDesk` (scoped to one
`Floor`) and `SecurityGate` (scoped to one `Branch`, optionally narrowed to
one `Building`), with the same branch-authorization and cross-branch 404
behavior as Building/Floor/Department. Each `ReceptionDesk` SHALL carry a
three-state operational status (`active`, `maintenance`, `inactive`) in
place of a plain active/inactive flag. Each `SecurityGate` SHALL carry a
three-state connectivity status (`online`, `maintenance`, `offline`)
alongside its existing entry/exit/both gate type, and MAY be flagged as a
high-security gate. `X-Branch-ID` SHALL be optional on every ReceptionDesk/
SecurityGate endpoint, following the same rules as Building/Floor/
Department: list endpoints scope to every authorized branch when it is
omitted, get/update/delete-by-id endpoints resolve authorization from the
target resource's own branch, creating a `SecurityGate` resolves the branch
from the body's `branchId`, and creating a `ReceptionDesk` resolves it
transitively from the body's `floorId`.

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
- **WHEN** a caller with `gates:manage` creates or updates a `SecurityGate`
  with `gateType: both` and `connectivityStatus: offline`
- **THEN** both values are stored independently, and neither field
  constrains the other's allowed values

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

### Requirement: Employee Directory Sync
The system SHALL provide a bulk, authoritative-batch employee-directory sync
endpoint that creates unknown employees, updates known ones, and deactivates
(never deletes) existing employees absent from the batch, validating every
referenced department before writing anything. The employee directory read
endpoint SHALL expose each employee's avatar image (when set) and their
current branch-role assignments, so a caller can render an employee's
identity and access level without a separate lookup per employee. Listing
employees SHALL treat `X-Branch-ID` as optional: when supplied, results are
scoped to that branch; when omitted, results are scoped to every branch the
caller is authorized for `employees:view` at (every branch, if held
company-wide).

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

#### Scenario: Listing employees without a branch header returns every authorized branch's employees
- **WHEN** a caller with `employees:view` company-wide sends
  `GET /employees` with no `X-Branch-ID` header
- **THEN** the response includes employees from every branch in the tenant

### Requirement: A Soft-Deleted Entity's Unique Code or Number Is Reusable
For every entity in this capability whose uniqueness is scoped by a code or
number (`Branch.code`, `Company.registration_number`,
`Building(branch_id, code)`, `Floor(building_id, floor_number)`,
`Department(branch_id, code)`, `ReceptionDesk(floor_id, code)`,
`SecurityGate(branch_id, code)`), the system SHALL enforce uniqueness only
among rows that are not soft-deleted, so that a new row may reuse the
code/number of a previously soft-deleted row of the same type.

#### Scenario: Recreating an entity with a soft-deleted row's code succeeds
- **WHEN** an entity of one of the types above is soft-deleted, and a new
  entity of the same type is then created with the same code/number (and,
  where applicable, the same parent scope)
- **THEN** the creation succeeds with 201, rather than failing on a
  database-level uniqueness violation

#### Scenario: A genuine duplicate among active rows is still rejected
- **WHEN** a create or update request would result in two *non-deleted* rows
  of the same type sharing the same code/number in the same scope
- **THEN** the request is rejected with 409, whether caught by the
  application-level pre-check or, in a concurrent-request race, by the
  database constraint itself

### Requirement: Company Email Is a Validated Email Address
`Company.email` SHALL be validated as a well-formed email address at the API
boundary, consistent with every other email field in this system.

#### Scenario: Malformed company email is rejected
- **WHEN** a caller submits a `Company` create or update request with an
  `email` value that is not a well-formed email address
- **THEN** the request is rejected with 422 before any database write
