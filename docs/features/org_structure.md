# Org Structure

Answers "what does this tenant's own org chart look like" as opposed to
`tenant/` (which answers "which tenant is this") — see `project-rules.md`'s
directory-structure note. The chart is a strict hierarchy, a project
decision made up front rather than left implicit:

```
Company (singleton) → Branch → Building → Floor → Department (optional)
                              → Department (direct, floor optional)
                              → SecurityGate (branch, optionally narrowed to one building)
                                Floor → ReceptionDesk
```

`Department` is scoped directly to a `Branch` (`branch_id`, required), with
an *optional* secondary `Floor` association (`floor_id`, nullable) — see
"Department is branch-scoped, not floor-scoped" below.

Every table here is tenant-scoped by schema (`Base`, not `GlobalBase`), same
as `Role`/`User` — see `database-architecture.md` §2.

## Field additions from the admin-portal design review

A design-vs-implementation review of the admin portal
(`openspec/changes/add-role-management-and-org-field-gaps/`) added:

- **`Branch`**: `city`, `country`, `contactPersonUserId`, `contactEmail`,
  `contactPhone`, `operatingHoursFrom`/`operatingHoursTo`, `notes`. `isActive`
  is now settable at creation, not only via a later update.
- **`Floor`**: `capacity` (int), `capacityType` (`guests`/`staff`),
  `accessLevel` (`public`/`restricted`/`secure`).
- **`ReceptionDesk`**: `status` (`active`/`maintenance`/`inactive`) replaced
  the boolean `isActive` — a maintenance desk isn't representable as a
  boolean. Also `assignedReceptionistUserId`,
  `operatingHoursFrom`/`operatingHoursTo`.
- **`SecurityGate`**: `connectivityStatus` (`online`/`maintenance`/`offline`)
  replaced the boolean `isActive`, for the same reason. Also `highSecurity`
  (bool, independent of `gateType`) and `authMethod` (free-form string for
  now — the design's compound values like "Biometric/RFID Card" aren't yet
  split into a clean enum; see the change's design doc Open Questions).
- **`Company`**: `defaultTimezone`, `autoApprovePreRegisteredVisitors`,
  `badgeExpiryDurationMinutes` — the "Organisation Configs" screen's
  tenant-wide visitor-policy defaults. Stored, not yet *read* by any other
  feature (e.g. the not-yet-built `checkin`/`approvals` features would be the
  ones to actually apply them).

## Soft-deleted rows free their code/number for reuse

`Branch.code`, `Company.registration_number`,
`Building(branch_id, code)`, `Floor(building_id, floor_number)`,
`Department(branch_id, code)`, `ReceptionDesk(floor_id, code)`, and
`SecurityGate(branch_id, code)` are each backed by a **partial** unique
index scoped to `deleted_at IS NULL` (`models.py`'s `_NOT_DELETED`), not an
unconditional one — so once a row is soft-deleted, a new row of the same
type may reuse its code/number. This matches what `repository.py`'s
`get_by_code`/`get_by_number` pre-checks already assumed (they filter
`deleted_at IS NULL` before deciding a code is free); before
`openspec/changes/harden-org-structure-crud`, the DB-level constraint
disagreed with that assumption and the soft-deleted code stayed reserved
forever, so the very next attempt to reuse it failed with an unhandled
`IntegrityError` instead of a clean 409. Every affected `service.py`
create/update path also wraps its `commit()` in an `IntegrityError` → 409
catch (`_commit_or_conflict`) as defense-in-depth against the residual
check-then-insert race between two concurrent requests.

## Department is branch-scoped, not floor-scoped

Originally `Department` was keyed to `floor_id` only. The admin portal's
department-creation design assigns a department directly to a `Branch` (a
Branch dropdown, no Floor step), so `Department.branch_id` is now a direct,
required FK, and `floor_id` is optional — a department can exist with no
floor at all. Uniqueness moved with it: `(branch_id, code)`, not
`(floor_id, code)`. See
`openspec/changes/add-role-management-and-org-field-gaps/design.md`
Decision 4 for the migration/backfill details (existing departments had
their `branch_id` backfilled from `floor -> building -> branch`).
`reports/repository.py`'s per-branch department/employee counts query
`Department.branch_id` directly for the same reason — a join through `Floor`
would silently miss any department with no `floor_id` set.

## Company is not `tenant.models.Tenant`

`Tenant` (global schema, `tenant/`) is the SaaS/schema boundary — "which
tenant is this," resolved from the JWT before any tenant table can even be
queried (`database-architecture.md` §2). `Company` is a *tenant-scoped*
table holding this tenant's own business identity: legal name, registration/
tax id, contact info, logo. Exactly one row is expected — enforced as a
business rule in `service.py` (`create_company` 409s if one already exists),
not a DB constraint, the same posture `Tenant` itself has today
(`database-architecture.md` §2's "exactly one row exists, but nothing assumes
there's only one").

Neither `Tenant` nor `Company` is what the Auth & Access requirement calls
"company_id" — that's `tenant_id`, carried on every token from day one for
future multi-tenant readiness. See `docs/features/auth.md`'s
"`tenant_id` is this system's 'company_id'" section for why.

## Endpoints

Company CRUD and Branch create/update/delete/provision are company-wide
only — you can't be "scoped to a branch" to create the branches themselves,
or to manage the company profile. `GET /branches` and `GET /branches/{id}`
are **not** part of that exception: they follow the same branch-scoped
pattern as every other list/get-by-id endpoint below. They used to depend
on the same company-wide-only `require_permission("branches:view")` as
create/update/delete, which meant a branch-scoped role (Reception/Security/
Host — assigned per branch, not company-wide, per
`security-architecture.md` §1) got 403'd on both, even though it holds
`branches:view` at its own branch. `list_branches` now depends on
`require_branch_scope("branches:view")` (same as Building/Department/...
below); `get_branch` now takes the caller and re-checks
`user.has_permission("branches:view", branch_id=branch.id)` after fetching
the row, 404-ing on failure — the same by-id pattern "Branch context" below
describes for every other entity.

Every Building/Floor/Department/ReceptionDesk/SecurityGate endpoint is
branch-scoped, and **`X-Branch-ID` is optional** on all of them (including
`GET /branches`/`GET /branches/{id}` now)
(`make-branch-header-optional-and-fix-roles-lookup` — see "Branch context"
below for exactly what happens when it's omitted):

- **Creating** a Building/Department/SecurityGate resolves the branch from
  the body's `branchId`; creating a Floor/ReceptionDesk resolves it
  transitively from `buildingId`/`floorId`. The header is never read here —
  sending it is harmless but has no effect.
- **Listing** is public — see "Listing endpoints require no token" below.
  Without the header, listing returns every branch's rows for the resolved
  tenant; sending the header still narrows to just that one branch.
- **Get/update/delete by id** without the header authorizes against the
  target's own (real) branch, resolved by looking it up — a caller with no
  access there gets 404, indistinguishable from the resource not existing.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/company` | `companies:manage` (company-wide) | Create the company profile. 409s if one already exists. |
| GET | `/api/v1/company` | `companies:view` (company-wide) | Fetch the company profile. 404s if not configured yet. |
| PUT | `/api/v1/company` | `companies:manage` (company-wide) | Update the company profile. |
| DELETE | `/api/v1/company` | `companies:manage` (company-wide) | Soft-delete the company profile. |
| POST | `/api/v1/branches` | `branches:manage` (company-wide) | Create a branch. |
| POST | `/api/v1/branches/provision` | `branches:provision` (company-wide) | Bulk-bootstrap a branch plus its Building → Floor → Department/ReceptionDesk chain and SecurityGates in one transaction. |
| GET | `/api/v1/branches` | Public (no token) | Paginated, sortable list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant. |
| GET | `/api/v1/branches/current` | `branches:view` at the resolved branch | Resolves the branch named by `X-Branch-ID` (still required here — there's no id/body field to resolve one from); confirms the caller has access. |
| GET | `/api/v1/branches/{id}` | `branches:view` at the branch's own id | Fetch one branch; 404 if the caller has no access to it. |
| PUT | `/api/v1/branches/{id}` | `branches:manage` (company-wide) | Update a branch. |
| DELETE | `/api/v1/branches/{id}` | `branches:manage` (company-wide) | Soft-delete a branch. |
| POST | `/api/v1/buildings` | `buildings:manage` at `branchId` (body) | Create a building. |
| GET | `/api/v1/buildings` | Public (no token) | Paginated list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant. |
| GET/PUT/DELETE | `/api/v1/buildings/{id}` | `buildings:view`/`buildings:manage` at the building's own branch | Fetch/update/soft-delete; 404 if the caller has no access to that branch. |
| POST | `/api/v1/floors` | `floors:manage` at the branch resolved from `buildingId` | Create a floor. |
| GET | `/api/v1/floors` | Public (no token) | Paginated list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant; optionally narrowed by `buildingId`. |
| GET/PUT/DELETE | `/api/v1/floors/{id}` | `floors:view`/`floors:manage` at the floor's own branch | Fetch/update/soft-delete; 404 if the caller has no access to that branch. |
| POST | `/api/v1/departments` | `departments:manage` at `branchId` (body) | Create a department. `floorId` is optional — if given, it must resolve to the same branch. |
| GET | `/api/v1/departments` | Public (no token) | Paginated list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant (`Department.branch_id` directly); optionally narrowed by `floorId`. |
| GET/PUT/DELETE | `/api/v1/departments/{id}` | `departments:view`/`departments:manage` at the department's own branch | Fetch/update/soft-delete; 404 if the caller has no access to that branch. |
| POST | `/api/v1/reception-desks` | `desks:manage` at the branch resolved from `floorId` | Create a reception desk. |
| GET | `/api/v1/reception-desks` | Public (no token) | Paginated list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant; optionally narrowed by `floorId`. |
| GET/PUT/DELETE | `/api/v1/reception-desks/{id}` | `desks:view`/`desks:manage` at the desk's own branch | Fetch/update/soft-delete; 404 if the caller has no access to that branch. |
| POST | `/api/v1/security-gates` | `gates:manage` at `branchId` (body) | Create a security gate; `buildingId`, if given, must belong to that same branch. |
| GET | `/api/v1/security-gates` | Public (no token) | Paginated list; scoped to `X-Branch-ID` if sent, else every branch in the resolved tenant; optionally narrowed by `buildingId`. |
| GET/PUT/DELETE | `/api/v1/security-gates/{id}` | `gates:view`/`gates:manage` at the gate's own branch | Fetch/update/soft-delete; 404 if the caller has no access to that branch. |

Every list endpoint follows `api-conventions.md` §1: `page`/`pageSize` query
params (`core/deps.py::get_pagination`), a `{data, pagination}` response
envelope (`core/responses.py::paginated_response`), and an explicit
`sortBy`/`sortOrder` whitelist (`name`/`created_at` — every entity here has
both columns) rather than a raw client-supplied sort string. There's no
`branchId` query param on the Building/SecurityGate lists — it would be
redundant with (and a way to bypass) `X-Branch-ID`, which still pins the
branch for the whole request when sent.

Every create/update/delete above queues an `AuditLog` write
(`auth/audit.py::record_audit_log`) as a `BackgroundTasks` task, per
`security-architecture.md` §5.

## Bulk provisioning (`POST /branches/provision`)

Plain `POST /branches` only ever creates the bare `Branch` row — standing up
a whole location (its buildings, floors, departments, reception desks,
gates) still meant one client-side round trip per entity. `provision_branch`
(`service.py`) accepts one nested request describing the whole tree and
creates it all in a single transaction: every row's id is generated
up front (`uuid.uuid4()`), so child rows can reference a not-yet-committed
parent's id directly, and the whole tree is committed exactly once — a
failed uniqueness check partway through (against existing rows, or against
a sibling within the same request) leaves nothing committed, rather than a
partially-provisioned branch to clean up by hand. Gated by its own
`branches:provision` permission (granted to Admin only), not
`branches:manage` — this is a materially bigger blast radius than renaming
one branch.

## Why one router module, several `APIRouter`s

`router.py` composes a distinct `APIRouter` per entity (`company_router`,
`branch_router`, `building_router`, ...), each with its own path prefix, then
combines them into the single `router` the rest of the app imports via
`router.include_router(...)`. A single flat `APIRouter()` (the pattern every
other feature here still uses) would work too, but splitting by entity kept
each block — and its permission dependencies — easy to scan on its own
once the feature grew past one entity.

## Branch context: the `X-Branch-ID` header is optional

`X-Branch-ID` still exists — a client may send it to pin a request to one
branch — but it is not required on any branch/location-scoped endpoint
(`make-branch-header-optional-and-fix-roles-lookup`). Which of three
resolution paths applies depends on the kind of request:

- **List** (`GET` with no id): `org_structure/deps.py::require_branch_scope(code)`
  reads the header if present (same 404/403 checks as before, narrowed to
  that one branch) or, if absent, calls
  `auth/models.py::User.authorized_branch_ids(code)` — "every branch" for a
  company-wide grant, otherwise the specific set of branches the caller
  holds `code` at (empty → 403). Either way the result is a `BranchScope`
  (`core/schemas.py`) the repository filters by — `column IN (...)`, or no
  filter at all for "every branch."
- **Get/update/delete by id**: no branch dependency at all. The route
  depends on plain `get_current_user`; the service function fetches the
  entity first, then checks `user.has_permission(code,
  branch_id=<the entity's real branch>)` itself, 404-ing (not 403) on
  failure — so a caller can't distinguish "doesn't exist" from "exists, but
  not in a branch you can access." This is a deliberate simplification over
  the old two-step (resolve header's branch, then separately verify the
  target actually belongs there): the id already pins the branch, so
  there's nothing left for a header to resolve or contradict.
- **Create**: also no header. `org_structure/deps.py::authorize_branch_id`
  runs the same 404 (branch missing/inactive) / 403 (no grant) checks as
  the list path's header-present branch, but takes an already-known branch
  id instead of reading one from a header — `payload.branch_id` directly
  for Building/Department/SecurityGate, or resolved transitively via
  `resolve_building_branch_id`/`resolve_floor_branch_id` for Floor/
  ReceptionDesk.

`org_structure/deps.py::get_branch_context`/`require_branch_permission`
(header required, unchanged) still exist for the one endpoint with no other
way to resolve a branch: `POST /invitations` (`docs/features/invitations.md`)
and `GET /branches/current`, which exists specifically to answer "what
branch does this header currently resolve to."

`structlog`'s contextvars still get `branch_id` bound wherever a branch is
actually resolved (header-present list requests, and creates), so log lines
for the rest of that request carry it alongside
`request_id`/`tenant_id`/`user_id` (`logging-observability.md` §2) — a
header-omitted list request scoped to "every branch" has no single
`branch_id` to bind, by design.

## Listing endpoints require no token

`GET /branches`, `/buildings`, `/floors`, `/departments`, `/reception-desks`,
and `/security-gates` (`fix-public-org-listings-and-email-diagnostics`) no
longer require a bearer token or any permission check — the web/mobile
clients need to render these lists (e.g. a branch/department picker) before
a visitor has authenticated, and were hitting "Invalid or expired token"
trying to. Get-by-id, create, update, delete, and `/branches/provision` are
unaffected — still authenticated and permissioned exactly as before.

`org_structure/deps.py::public_tenant_db` resolves which tenant a listing
request sees:

- If the request carries a valid access token, its `tenant_id` claim wins —
  an already-authenticated caller keeps listing its own tenant's data, not
  the deployment's default one.
- Otherwise (no token, or one that's expired/malformed/doesn't resolve to a
  real, active tenant) it falls back to the deployment's configured default
  tenant (`settings.default_tenant_slug`), the same single-tenant-today
  posture `invitations/deps.py::track_default_tenant_db` and
  `identity_verification/deps.py::default_tenant_id` already use for their
  own public endpoints.

`org_structure/deps.py::public_branch_scope` replaces
`require_branch_scope` on these six endpoints: `X-Branch-ID`, if present,
still narrows to that one branch (404 if it doesn't exist or is inactive);
if absent, every branch in the resolved tenant is in scope — there's no
caller to compute an authorized subset for. All six remain rate-limited by
client IP (`core/rate_limit.py::limiter`, 60/minute), consistent with every
other unauthenticated endpoint in this API.

## Why this isn't in `core`

Branch-context resolution is genuinely cross-cutting (every branch-scoped
feature will need it, the same way tenant/user resolution is), but
`fastapi-architecture.md` §6 restricts `core`'s upward dependencies to
`auth`/`tenant` only. Rather than carve out another exception, the
branch-context dependencies live in `org_structure/deps.py` itself; a feature
router imports `require_branch_permission` from there directly, the same way
it already imports `require_permission` from `core.deps`.
