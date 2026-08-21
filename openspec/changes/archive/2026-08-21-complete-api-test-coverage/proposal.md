## Why

API-01 through API-15 are now all implemented (auth, tenant, platform,
org_structure, visitors, invitations, registrations, reports,
identity_verification), and prior changes (`audit-and-expand-api-test-coverage`,
`close-api-test-coverage-gaps`, `reverify-api-test-suite`, `verify-invitation-...`,
`verify-platform-reliability-apis` — all archived) already closed several
specific coverage gaps found by ad-hoc spot-checks. What's never been done is a
**single, systematic pass across every one of the 15 features, ordered by the
actual visitor-lifecycle workflow** (provision tenant → authenticate/RBAC → set
up org structure → configure visitor types → invite/register a visitor → verify
identity → approve → report), checking every endpoint against
`testing-standards.md` §2's full bar (happy path, permission-denied,
tenant-isolation) in that order, plus every request-validation and error-path
scenario an automation tester would exercise (invalid input, duplicate/conflict,
not-found, rate-limit, idempotency replay) — rather than another spot-check that
finds 2-3 gaps and stops. The most recently added feature,
`identity_verification` (API-15, archived 2026-08-21), has not been through any
audit pass yet.

**Scope note on "15 APIs":** the user's "15 API's" maps to the informal
`API-01`..`API-15` backlog numbering already used in commit messages and
feature docstrings (confirmed via `git log`, `close-api-test-coverage-gaps`'s
proposal, and inline `API-0N` markers in router/deps modules) — one numbered
unit per feature package, not 15 individual HTTP endpoints. The actual surface
is ~60+ endpoints across 9 feature packages. This proposal treats "sort the
APIs according to functionality" as sorting those 9 packages into the workflow
order above, and treats "every scenario" as testing-standards.md §2's bar plus
the error/edge-case scenarios listed in design.md.

## What Changes

- Produce one workflow-ordered test matrix (`design.md`) enumerating every
  endpoint across all 9 feature packages, grouped into the 7 lifecycle stages
  below, with its expected scenarios (happy path, permission-denied or
  public-auth-equivalent, tenant-isolation or its documented non-applicability,
  validation/conflict/not-found, and rate-limit/idempotency where the endpoint
  has one).
- Run the full existing suite first to get a real baseline (not an assumed
  "last known count" carried over from an archived change), then systematically
  compare it against the matrix, feature by feature, in workflow order:
  1. **Provisioning** — `platform` (superadmin login, tenant create/list),
     `tenant` (self-view).
  2. **Auth/RBAC** — `auth` (login, users, branch-roles, employee sync,
     permission catalog, roles CRUD).
  3. **Org structure** — `org_structure` (company, branch, branch provision,
     building, floor, department, desk, gate).
  4. **Visitor-type config** — `visitors` (visitor categories, approval-workflow
     rules).
  5. **Invitation & walk-in intake** — `invitations` (create, public track),
     `registrations` (walk-in).
  6. **Identity verification** — `identity_verification` (OTP request/verify).
  7. **Reporting** — `reports` (branch rollup).
- Add the specific missing test cases the matrix identifies. Two are already
  known from the initial survey and belong in the matrix regardless of what the
  full pass turns up:
  - `tenant` feature has no tenant-isolation test despite `testing-standards.md`
    §2 nominally requiring one per feature (likely resolves as a documented
    non-applicability, same reasoning as `platform` — global-schema-only
    repositories — but that reasoning needs to be written down and asserted,
    not assumed).
  - `identity_verification`'s Redis-keyed per-tenant state (OTP codes, rate-limit
    counters) has no test proving tenant A's state can't collide with tenant
    B's under the `vmss:{tenant_id}:...` key convention — unlike every other
    feature, its "tenant isolation" is a Redis key-namespace property, not a
    Postgres schema property, so it needs its own kind of isolation test.
  - Every other package's exact gaps are determined by running the matrix
    against current tests, not assumed up front.
- Where a gap check surfaces an actual bug (an endpoint behaving differently
  from its documented/intended contract — not a missing test), fix it as part
  of this change, following the precedent set by `close-api-test-coverage-gaps`
  (e.g. that change's `sync_employee_directory` duplicate-employee 500-instead-
  of-409 fix, and the invitations orphaned-file-upload fix). `design.md` defines
  the stop-and-report threshold for when a "gap" is actually a bug fix vs. a
  behavior change big enough to need its own proposal.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None planned. Adding tests for scenarios that are already part of each
endpoint's existing, intended contract does not change spec-level behavior.
Fixing a bug so an endpoint matches its already-documented/intended contract
(same class of fix as the precedent above) is also not a spec change. If the
audit surfaces a case where the *intended* contract itself is ambiguous or
needs to change, that is out of scope for this change and gets flagged as a
follow-up (see design.md), not folded in silently. This change sets
`skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **Affected code**: potentially every feature's `tests.py`
  (`auth`, `tenant`, `platform`, `org_structure`, `visitors`, `invitations`,
  `registrations`, `reports`, `identity_verification`) plus
  `tests/test_api_documentation.py` for cross-cutting checks — exact files
  depend on what the systematic pass finds missing.
- **Possible production-code fixes**: only if the audit finds a real bug
  (endpoint not matching its intended contract), scoped to the specific
  service/router file involved — not a refactor pass.
- **No dependency, schema, or migration changes.**
- **No breaking changes.**
