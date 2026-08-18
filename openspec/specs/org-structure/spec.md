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

### Requirement: Branch, Building, Floor, and Department CRUD
The system SHALL provide full CRUD for `Branch` (company-wide) and for
`Building`/`Floor`/`Department` (branch-scoped, forming a strict
Branch → Building → Floor → Department hierarchy), rejecting any request
whose target does not actually belong to the caller's authorized branch.
The system SHALL additionally provide a bulk provisioning operation that
creates a new `Branch` together with as much of its
Building → Floor → Department/ReceptionDesk chain and SecurityGates as a
single request supplies, in one transaction.

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

### Requirement: Reception Desk and Security Gate CRUD
The system SHALL provide full CRUD for `ReceptionDesk` (scoped to one
`Floor`) and `SecurityGate` (scoped to one `Branch`, optionally narrowed to
one `Building`), with the same branch-authorization and cross-branch 404
behavior as Building/Floor/Department.

#### Scenario: Security gate optionally narrowed to a building
- **WHEN** a `SecurityGate` is created with a `buildingId` that does not
  belong to the gate's `branchId`
- **THEN** the request is rejected with 404

### Requirement: Employee Directory Sync
The system SHALL provide a bulk, authoritative-batch employee-directory sync
endpoint that creates unknown employees, updates known ones, and deactivates
(never deletes) existing employees absent from the batch, validating every
referenced department before writing anything.

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

### Requirement: A Soft-Deleted Entity's Unique Code or Number Is Reusable
For every entity in this capability whose uniqueness is scoped by a code or
number (`Branch.code`, `Company.registration_number`,
`Building(branch_id, code)`, `Floor(building_id, floor_number)`,
`Department(floor_id, code)`, `ReceptionDesk(floor_id, code)`,
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
