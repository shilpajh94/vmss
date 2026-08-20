## MODIFIED Requirements

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
- **WHEN** a caller requests, updates, or deletes a Building/Floor/
  Department by id that belongs to a branch the caller holds no grant at
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
- **WHEN** a `SecurityGate` is created or updated with a `buildingId`
- **THEN** the system rejects the request with 404 if that building does not
  belong to the gate's `branchId`

#### Scenario: A reception desk can be set to maintenance status
- **WHEN** a caller with `desks:manage` updates a `ReceptionDesk`'s status to
  `maintenance`
- **THEN** the desk's status is updated and reflected in subsequent reads

#### Scenario: A security gate's connectivity status is independent of its gate type
- **WHEN** a caller with `gates:manage` updates a `SecurityGate`'s
  `connectivityStatus`
- **THEN** the gate's `gateType` is unaffected by the update

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
- **WHEN** an employee-directory sync batch references a `departmentId` that
  does not exist in the tenant's schema
- **THEN** the entire batch is rejected and no employee row is created,
  updated, or deactivated

#### Scenario: Employee absent from an authoritative batch is deactivated, not deleted
- **WHEN** an existing employee's record is absent from a new authoritative
  sync batch
- **THEN** the employee is marked inactive, and its row (and audit history)
  is retained

#### Scenario: Listing employees includes avatar and role assignments
- **WHEN** a caller with `employees:view` lists employees for a branch
- **THEN** each employee in the response includes their avatar URL (if set)
  and the list of its current branch-role assignments (role name and
  branch, if any)

#### Scenario: Listing employees without a branch header returns every authorized branch's employees
- **WHEN** a caller with `employees:view` company-wide sends
  `GET /employees` with no `X-Branch-ID` header
- **THEN** the response includes employees from every branch in the tenant
