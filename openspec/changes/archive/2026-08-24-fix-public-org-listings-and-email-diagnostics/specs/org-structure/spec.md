## MODIFIED Requirements

### Requirement: Branch, Building, Floor, and Department CRUD
The system SHALL provide full CRUD for `Branch` (company-wide) and for
`Building`/`Floor`/`Department` (branch-scoped), rejecting any authenticated
get-by-id/update/delete request whose target does not actually belong to a
branch the caller is authorized for. A `Department` SHALL be creatable
directly under a `Branch`, with an optional `Floor` association rather than
a mandatory one — a department is not required to be assigned to a specific
floor to exist. The system SHALL additionally provide a bulk provisioning
operation that creates a new `Branch` together with as much of its Building
→ Floor → Department/ReceptionDesk chain and SecurityGates as a single
request supplies, in one transaction. `Branch` and `Building` SHALL accept
their active/inactive status at creation time, not only via a later update.
Listing `Branch`/`Building`/`Floor`/`Department` is public (see "Master-Data
Listing Endpoints Are Public" below); `X-Branch-ID` on those list endpoints
narrows results to one branch when supplied, or otherwise every branch's
rows for the tenant is returned. `X-Branch-ID` on get/update/delete-by-id
endpoints continues to resolve authorization from the target resource's own
branch, unchanged; creating a `Building`/`Department` still resolves the
branch from the body's `branchId`, and creating a `Floor` still resolves it
transitively from the body's `buildingId`.

#### Scenario: Branch-scoped entity outside the authorized branch is hidden as 404
- **WHEN** a caller authorized at Branch A requests, updates, or deletes a
  Building/Floor/Department that actually belongs to Branch B (by id or
  path)
- **THEN** the request is rejected with 404, not 403 — indistinguishable
  from the target not existing at all

#### Scenario: A single company operates multiple branches
- **WHEN** more than one `Branch` row exists in a tenant's schema
- **THEN** every branch-scoped entity (Building/Floor/Department/
  ReceptionDesk/SecurityGate) correctly resolves to exactly one owning
  branch, and a listing narrowed by `X-Branch-ID` for one branch never
  includes another branch's rows

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
- **WHEN** a client sends `GET /buildings` with no `X-Branch-ID` header
- **THEN** the response includes buildings from every branch in the
  tenant — listing requires no permission check, so every branch is, by
  definition, within scope, regardless of any token presented or omitted

#### Scenario: Listing buildings without a branch header, for a branch-restricted caller, is scoped to their branches
- **WHEN** a client sends `GET /buildings` with an `X-Branch-ID` header
  naming one existing, active branch instead of omitting it
- **THEN** the response is restricted to that one branch's rows — the only
  way to narrow this now-public listing to fewer than every branch,
  regardless of any token presented or omitted

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
behavior as Building/Floor/Department for every get-by-id/update/delete
request. Each `ReceptionDesk` SHALL carry a three-state operational status
(`active`, `maintenance`, `inactive`) in place of a plain active/inactive
flag. Each `SecurityGate` SHALL carry a three-state connectivity status
(`online`, `maintenance`, `offline`) alongside its existing entry/exit/both
gate type, and MAY be flagged as a high-security gate. `X-Branch-ID` SHALL
be optional on every ReceptionDesk/SecurityGate endpoint. Listing
`ReceptionDesk`/`SecurityGate` is public (see "Master-Data Listing Endpoints
Are Public" below); get/update/delete-by-id endpoints continue to resolve
authorization from the target resource's own branch, creating a
`SecurityGate` resolves the branch from the body's `branchId`, and creating
a `ReceptionDesk` resolves it transitively from the body's `floorId`.

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

## ADDED Requirements

### Requirement: Master-Data Listing Endpoints Are Public
Listing `Branch`, `Building`, `Floor`, `Department`, `ReceptionDesk`, and
`SecurityGate` SHALL require no bearer token and no permission check — a
web/mobile client SHALL be able to fetch these lists (e.g. to populate a
branch or department picker) before a visitor has authenticated. When the
request carries a valid access token, these endpoints SHALL resolve the
tenant from that token's `tenant_id` claim, the same tenant an authenticated
request would resolve to — so an already-logged-in caller keeps listing its
own tenant's data. When no token is presented, or the presented token does
not resolve to a real, active tenant, these endpoints SHALL instead resolve
the deployment's configured default tenant; either way, no permission
check applies. An optional `X-Branch-ID` header SHALL narrow results to
that one branch (404 if it does not exist or is inactive); omitting it
SHALL return every branch's rows for the resolved tenant, with no notion of
a caller's authorized branches. Get-by-id, create, update, and delete
endpoints for these six entities are unaffected and remain authenticated
and permissioned as before. These endpoints SHALL remain rate-limited by
client IP per the posture `security-architecture.md` §2 requires for
unauthenticated endpoints.

#### Scenario: Listing master data requires no Authorization header
- **WHEN** a client calls a branch/building/floor/department/reception-desk/
  security-gate list endpoint with no `Authorization` header at all
- **THEN** the request succeeds, resolving the deployment's default tenant,
  rather than failing with 401

#### Scenario: An expired or invalid token no longer blocks listing
- **WHEN** a client calls one of these list endpoints while presenting an
  expired, malformed, or otherwise invalid bearer token
- **THEN** the request still succeeds, falling back to the deployment's
  default tenant exactly as if no token had been presented

#### Scenario: A valid token's own tenant takes precedence over the default tenant
- **WHEN** an authenticated caller whose access token belongs to a tenant
  other than the deployment's configured default calls one of these list
  endpoints
- **THEN** the response reflects that caller's own tenant, not the default
  tenant — an authenticated admin of a second tenant lists its own branches,
  never the default tenant's

#### Scenario: Listing without X-Branch-ID returns every branch's rows for the tenant
- **WHEN** a client calls one of these list endpoints with no `X-Branch-ID`
  header
- **THEN** the response includes matching rows from every branch in the
  tenant, regardless of any token presented

#### Scenario: Listing with X-Branch-ID narrows to one branch
- **WHEN** a client calls one of these list endpoints with an `X-Branch-ID`
  header naming an existing, active branch
- **THEN** the response includes only rows belonging to that branch

#### Scenario: Listing with an unknown or inactive X-Branch-ID is rejected
- **WHEN** a client calls one of these list endpoints with an `X-Branch-ID`
  header naming a branch that does not exist, or is inactive, in the
  resolved tenant
- **THEN** the request is rejected with 404

#### Scenario: Public listing never crosses tenant boundaries
- **WHEN** a client calls one of these list endpoints
- **THEN** the response includes only rows from the single tenant the
  request resolves to, never rows from any other tenant's schema

#### Scenario: Excessive listing requests are rate-limited
- **WHEN** a client exceeds the configured rate limit for one of these list
  endpoints from a single IP
- **THEN** further requests are rejected with 429 until the window resets
