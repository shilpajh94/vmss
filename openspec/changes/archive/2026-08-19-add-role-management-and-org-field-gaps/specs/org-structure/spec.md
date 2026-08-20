## MODIFIED Requirements

### Requirement: Branch, Building, Floor, and Department CRUD
The system SHALL provide full CRUD for `Branch` (company-wide) and for
`Building`/`Floor`/`Department` (branch-scoped), rejecting any request whose
target does not actually belong to the caller's authorized branch. A
`Department` SHALL be creatable directly under a `Branch`, with an optional
`Floor` association rather than a mandatory one — a department is not
required to be assigned to a specific floor to exist. The system SHALL
additionally provide a bulk provisioning operation that creates a new
`Branch` together with as much of its Building → Floor → Department/
ReceptionDesk chain and SecurityGates as a single request supplies, in one
transaction. `Branch` and `Building` SHALL accept their active/inactive
status at creation time, not only via a later update.

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

### Requirement: Reception Desk and Security Gate CRUD
The system SHALL provide full CRUD for `ReceptionDesk` (scoped to one
`Floor`) and `SecurityGate` (scoped to one `Branch`, optionally narrowed to
one `Building`), with the same branch-authorization and cross-branch 404
behavior as Building/Floor/Department. Each `ReceptionDesk` SHALL carry a
three-state operational status (`active`, `maintenance`, `inactive`) in
place of a plain active/inactive flag. Each `SecurityGate` SHALL carry a
three-state connectivity status (`online`, `maintenance`, `offline`)
alongside its existing entry/exit/both gate type, and MAY be flagged as a
high-security gate.

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

## ADDED Requirements

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
