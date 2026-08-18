# Org Structure

Answers "what does this tenant's own org chart look like" as opposed to
`tenant/` (which answers "which tenant is this") — see `project-rules.md`'s
directory-structure note. The chart is a strict hierarchy, a project
decision made up front rather than left implicit:

```
Company (singleton) → Branch → Building → Floor → Department
                              → SecurityGate (branch, optionally narrowed to one building)
                                Floor → ReceptionDesk
```

Every table here is tenant-scoped by schema (`Base`, not `GlobalBase`), same
as `Role`/`User` — see `database-architecture.md` §2.

## Soft-deleted rows free their code/number for reuse

`Branch.code`, `Company.registration_number`,
`Building(branch_id, code)`, `Floor(building_id, floor_number)`,
`Department(floor_id, code)`, `ReceptionDesk(floor_id, code)`, and
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

Company and Branch CRUD are company-wide only — you can't be "scoped to a
branch" to create the branches themselves. Every Building/Floor/Department/
ReceptionDesk/SecurityGate endpoint is branch-scoped: it requires an
`X-Branch-ID` header (422 if missing) and rejects, as a 404, any request
whose target doesn't actually belong to that branch — see "Branch context"
below.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/company` | `companies:manage` (company-wide) | Create the company profile. 409s if one already exists. |
| GET | `/api/v1/company` | `companies:view` (company-wide) | Fetch the company profile. 404s if not configured yet. |
| PUT | `/api/v1/company` | `companies:manage` (company-wide) | Update the company profile. |
| DELETE | `/api/v1/company` | `companies:manage` (company-wide) | Soft-delete the company profile. |
| POST | `/api/v1/branches` | `branches:manage` (company-wide) | Create a branch. |
| POST | `/api/v1/branches/provision` | `branches:provision` (company-wide) | Bulk-bootstrap a branch plus its Building → Floor → Department/ReceptionDesk chain and SecurityGates in one transaction. |
| GET | `/api/v1/branches` | `branches:view` (company-wide) | Paginated, sortable list of branches. |
| GET | `/api/v1/branches/current` | `branches:view` at the resolved branch | Resolves the branch named by `X-Branch-ID`; confirms the caller has access. |
| GET | `/api/v1/branches/{id}` | `branches:view` (company-wide) | Fetch one branch. |
| PUT | `/api/v1/branches/{id}` | `branches:manage` (company-wide) | Update a branch. |
| DELETE | `/api/v1/branches/{id}` | `branches:manage` (company-wide) | Soft-delete a branch. |
| POST | `/api/v1/buildings` | `buildings:manage` at `X-Branch-ID` | Create a building; `branchId` in the body must match `X-Branch-ID`. |
| GET | `/api/v1/buildings` | `buildings:view` at `X-Branch-ID` | Paginated list, always scoped to `X-Branch-ID`. |
| GET/PUT/DELETE | `/api/v1/buildings/{id}` | `buildings:view`/`buildings:manage` at `X-Branch-ID` | Fetch/update/soft-delete; 404 if the building isn't in that branch. |
| POST | `/api/v1/floors` | `floors:manage` at `X-Branch-ID` | Create a floor; the target building must belong to `X-Branch-ID`. |
| GET | `/api/v1/floors` | `floors:view` at `X-Branch-ID` | Paginated list, scoped to `X-Branch-ID`, optionally narrowed by `buildingId`. |
| GET/PUT/DELETE | `/api/v1/floors/{id}` | `floors:view`/`floors:manage` at `X-Branch-ID` | Fetch/update/soft-delete; 404 if the floor's building isn't in that branch. |
| POST | `/api/v1/departments` | `departments:manage` at `X-Branch-ID` | Create a department; the target floor must resolve to `X-Branch-ID`. |
| GET | `/api/v1/departments` | `departments:view` at `X-Branch-ID` | Paginated list, scoped to `X-Branch-ID`, optionally narrowed by `floorId`. |
| GET/PUT/DELETE | `/api/v1/departments/{id}` | `departments:view`/`departments:manage` at `X-Branch-ID` | Fetch/update/soft-delete; 404 if outside that branch. |
| POST | `/api/v1/reception-desks` | `desks:manage` at `X-Branch-ID` | Create a reception desk; the target floor must resolve to `X-Branch-ID`. |
| GET | `/api/v1/reception-desks` | `desks:view` at `X-Branch-ID` | Paginated list, scoped to `X-Branch-ID`, optionally narrowed by `floorId`. |
| GET/PUT/DELETE | `/api/v1/reception-desks/{id}` | `desks:view`/`desks:manage` at `X-Branch-ID` | Fetch/update/soft-delete; 404 if outside that branch. |
| POST | `/api/v1/security-gates` | `gates:manage` at `X-Branch-ID` | Create a security gate; `branchId` in the body must match `X-Branch-ID` (and `buildingId`, if given). |
| GET | `/api/v1/security-gates` | `gates:view` at `X-Branch-ID` | Paginated list, always scoped to `X-Branch-ID`, optionally narrowed by `buildingId`. |
| GET/PUT/DELETE | `/api/v1/security-gates/{id}` | `gates:view`/`gates:manage` at `X-Branch-ID` | Fetch/update/soft-delete; 404 if outside that branch. |

Every list endpoint follows `api-conventions.md` §1: `page`/`pageSize` query
params (`core/deps.py::get_pagination`), a `{data, pagination}` response
envelope (`core/responses.py::paginated_response`), and an explicit
`sortBy`/`sortOrder` whitelist (`name`/`created_at` — every entity here has
both columns) rather than a raw client-supplied sort string. There's no
`branchId` query param on the Building/SecurityGate lists — it would be
redundant with (and a way to bypass) `X-Branch-ID`, which already pins the
branch for the whole request.

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

## Branch context: the `X-Branch-ID` header

Every branch/location-scoped request carries an `X-Branch-ID` header naming
which branch it operates against — not a JWT claim. A user who works across
branches in one login session (a roaming Security guard, an Admin) switches
branch per request instead of re-authenticating; see
`security-architecture.md` §1.

`org_structure/deps.py::get_branch_context` resolves and authorizes it:
loads the `Branch` the header names, 404s if it doesn't exist (or is
inactive) in this tenant, and 403s if the caller has no role grant there
(`auth/models.py::User.has_branch_access`). It also binds `branch_id` into
`structlog`'s contextvars, so every log line for the rest of the request
carries it alongside `request_id`/`tenant_id`/`user_id`
(`logging-observability.md` §2).

`require_branch_permission(code)` builds on it — the branch-scoped
counterpart to `core.deps.require_permission(code)` — granting when the
caller holds `code` either company-wide or specifically at that branch (see
`auth/models.py::User.has_permission`). Any future branch-scoped feature
(check-in, visitor management, ...) depends on `org_structure.deps`, not
`core.deps`, for this — see the note in `fastapi-architecture.md` §6 on why
`core` doesn't import feature packages other than `auth`/`tenant`.

A resolved `X-Branch-ID` only proves the caller may act *at that branch* —
it says nothing about whether the specific building/floor/department/desk/
gate a request targets actually belongs there. `require_branch_permission`
alone would let a Reception user authorized at Branch A reach into Branch
B's resources just by naming Branch A's header while pointing the request
body/path at a Branch B id. Every mutating and read endpoint in
`org_structure/service.py` closes that gap itself: it resolves the target's
*real* branch (`Building.branch_id` directly; `Floor`/`Department`/
`ReceptionDesk` by walking `building_id`/`floor_id` up to the owning
`Building`) and 404s — not 403 — on a mismatch, so a branch-scoped caller
can't distinguish "doesn't exist" from "exists, but not in your branch."
List endpoints get the same treatment via a repository-level join back to
`Building` (`org_structure/repository.py`), so a branch-scoped list never
returns another branch's rows regardless of query filters.

## Why this isn't in `core`

Branch-context resolution is genuinely cross-cutting (every branch-scoped
feature will need it, the same way tenant/user resolution is), but
`fastapi-architecture.md` §6 restricts `core`'s upward dependencies to
`auth`/`tenant` only. Rather than carve out another exception, the
branch-context dependencies live in `org_structure/deps.py` itself; a feature
router imports `require_branch_permission` from there directly, the same way
it already imports `require_permission` from `core.deps`.
