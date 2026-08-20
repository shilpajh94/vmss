## Context

Every branch-scoped route today depends on `org_structure/deps.py`'s
`get_branch_context`/`require_branch_permission(code)`: a required
`x_branch_id: Annotated[uuid.UUID, Header(alias="X-Branch-ID")]` parameter
(no default, so FastAPI 422s if it's missing) resolves one `Branch` up
front, checked with `user.has_branch_access` and
`user.has_permission(code, branch_id=branch.id)` before the route body runs.
Every list-repository method (`BuildingRepository.list_page`,
`FloorRepository.list_page`, etc.) takes a single required `branch_id`
filter; every by-id service function (`get_building`, `update_floor`, ...)
takes an `authorized_branch_id` and 404s if the fetched row's branch
disagrees. `User.has_permission(code, branch_id=None)` checks a
company-wide grant only (`auth/models.py:96`); there is currently no way to
ask "which branches, if any, does this user hold `code` at" — that's the
one genuinely new piece of logic this change needs. See proposal.md for
motivation and the withdrawn alternative this replaces.

## Goals / Non-Goals

**Goals:**
- Make `X-Branch-ID` optional everywhere it's used today, with the
  omitted-header behavior spelled out per proposal.md (list vs. by-id vs.
  create), without changing what a caller who *does* send the header
  experiences.
- Add the one new authorization primitive this requires — "every branch a
  user holds `code` at" — in one place, reused by every list endpoint.
- Fix the roles permission-catalog discoverability gap independently of the
  branch-header work (unrelated code paths).

**Non-Goals:**
- Not changing `has_permission`'s existing single-branch check or
  `has_branch_access` — both are still correct and still used as-is for the
  header-present and by-id-resolved cases.
- Not adding a "default branch" concept to `User`/`UserBranchRole` — when a
  list is unscoped, it means "every branch I'm authorized for," not "my one
  preferred branch." (Rejected explicitly in the earlier clarifying
  question in favor of this simpler, no-new-state option.)
- Not touching `Idempotency-Key` behavior at all (see proposal.md) — no
  design content here.

## Decisions

### Decision 1: A new `User.authorized_branch_ids(code) -> BranchScope` helper
Add one method to `auth/models.py::User` returning a small result that is
either "all branches" (the caller holds `code` company-wide —
`has_permission(code, branch_id=None)` is `True`) or the explicit set of
branch ids drawn from `self.branch_roles` where the assignment's role
grants `code` and `assignment.branch_id is not None`. An empty set means no
access at all → the caller-facing behavior is 403, same as today's "no
grant" case. This is the single new piece of domain logic the whole change
depends on; every list endpoint below calls it once.

**Alternative considered**: compute the branch set inline in each router
function. Rejected — five endpoints (buildings, floors, departments, desks,
gates) plus employees would each reimplement the same branch_roles scan;
one method on `User` keeps the RBAC logic in one place per
`fastapi-architecture.md` §6's "don't scatter permission checks."

### Decision 2: Two dependency shapes replace one, split by request kind
`require_branch_permission(code)` (header required) is replaced by two
narrower dependencies in `org_structure/deps.py`, both taking an optional
header:

- `require_branch_scope(code)` — for list endpoints. Reads
  `x_branch_id: uuid.UUID | None = Header(None, alias="X-Branch-ID")`.
  If given, behaves exactly like today (404/403, returns a single resolved
  `Branch`). If omitted, calls `user.authorized_branch_ids(code)`; 403 if
  empty; otherwise returns a `BranchScope` (single branch, explicit set, or
  "all") that the route passes to its repository call.
- **(Corrected during implementation — see tasks.md §4.1)** By-id GET/PUT/
  DELETE routes drop the branch/permission dependency entirely rather than
  reusing `core.deps.require_permission(code)` as originally planned here:
  that dependency only matches a *company-wide* grant
  (`has_permission(code, branch_id=None)`), so it would 403 a legitimately
  branch-scoped caller before the target entity is even fetched — exactly
  backwards. Instead these routes depend on plain `get_current_user`, and
  the *service* function fetches the entity first, then checks
  `user.has_permission(code, branch_id=entity.branch_id)` itself,
  404-ing on failure (folding the old "wrong branch" 404 and "no grant at
  that branch" cases into one outcome, since there's no separately-declared
  target branch left to distinguish them by — see Risk below).
- Creation endpoints resolve branch from the body via the new
  `authorize_branch_id(tenant_db, user, code, branch_id)` helper (same
  404/403 checks as `get_branch_context`/`require_branch_permission`, just
  parameterized by an already-known branch id instead of a header) —
  `X-Branch-ID` is simply never read on these routes. `POST /invitations`
  is the one exception with no body branch field — it keeps
  `require_branch_permission`'s header-required behavior verbatim, but the
  422-on-missing-header default is replaced by an optional header plus an
  explicit 400 check, so the failure mode is a handled business error, not
  a framework-level validation error.

**Alternative considered**: one dependency returning a union type
(`Branch | BranchScope`) for every use site. Rejected — by-id routes don't
need branch resolution *at all* under this design (Decision 2's third
bullet resolves branch from the entity, not a dependency), so forcing them
through a branch-resolving dependency would just be unused work on every
call.

### Decision 3: Repository list methods accept a scope, not a single id
Each affected `list_page` (`BuildingRepository`, `FloorRepository`,
`DepartmentRepository`, `ReceptionDeskRepository`, `SecurityGateRepository`,
and the employee-listing query in `auth/repository.py`) changes its
`branch_id: uuid.UUID` parameter to accept the `BranchScope` from Decision
1/2: a single id (current behavior, unchanged filter), an explicit
`Collection[uuid.UUID]` (`WHERE branch_id IN (...)`), or "all" (no branch
filter at all — just the existing soft-delete/pagination filters). This is
a query-shape decision, not a query-count one — still exactly one query per
list call, satisfying `query-performance.md` §2 regardless of which scope
variant is used.

### Decision 4: By-id routes fold "wrong branch" and "no grant there" into one 404
Today, a caller who sends `X-Branch-ID` naming a branch they have zero grant
at gets 403 (from `get_branch_context`) even before the target resource is
looked up; a caller authorized at the *named* branch but targeting a
resource that actually belongs to a *different* branch gets 404 (existing
"hidden as 404" scenario). Once by-id routes stop pre-resolving a branch
from a header, there's no separately-asserted "named branch" left to be
wrong about — the only question is "is the caller authorized at the
resource's real branch," and the existing hidden-as-404 convention already
says failing that is a 404, not a 403. This is a deliberate narrowing of
the 403 case to list/create endpoints only (where a caller-named branch
genuinely exists to be wrong about); by-id endpoints uniformly 404 on any
access failure. Called out explicitly in the auth spec delta's new
"Omitting the header on a by-id request..." scenario.

### Decision 5: Roles/permissions fix is independent, same shape as before
`GET /api/v1/auth/permissions` (global-schema `PermissionRepository`,
gated by `roles:view`) and `examples=[...]` on
`RoleCreateRequest`/`RoleUpdateRequest.permissionCodes` — unchanged from the
withdrawn proposal's Decisions 5–6, since none of this was part of what got
reverted. Rejecting unknown codes stays 404, unchanged.

## Risks / Trade-offs

- **[Risk]** Folding "wrong branch" and "no access" into one 404 for by-id
  endpoints (Decision 4) means a legitimate permission-denial audit signal
  (`security-architecture.md` §5 — permission denials logged at `WARNING`)
  now looks identical to a not-found in the HTTP response, though the
  server-side log line still distinguishes them (the log records the actual
  resource id and the permission checked, per `logging-observability.md`
  §2). → No client-visible mitigation needed; this only changes what an
  unauthorized caller sees, not what's recorded.
- **[Risk]** `BranchScope`'s "all branches" case removes what was previously
  a mandatory filter from list queries — a bug in `authorized_branch_ids`
  that over-reports company-wide access would over-expose rows across
  branches. → Mitigate with the tenant-isolation-style test coverage
  `testing-standards.md` §2 already mandates: a dedicated test asserting a
  branch-restricted caller's unscoped list never includes another branch's
  rows, and a company-wide caller's unscoped list includes all of them.
- **[Trade-off]** Five repositories and one auth query gain a slightly
  wider parameter type (single id → id/set/"all"). This is more surface
  than the withdrawn proposal touched, but avoids adding a second, parallel
  set of "list across branches" methods.

## Migration Plan

- Single deploy, no data migration — this is a request-contract and
  authorization-logic change only.
- Rollback is a straight revert: `X-Branch-ID` reverting to required is
  backward compatible with any client that was still sending it (nothing in
  this design tells clients to stop sending it, only that they may).
