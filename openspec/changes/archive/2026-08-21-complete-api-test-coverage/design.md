## Context

See `proposal.md` - Why for motivation and the "15 APIs" scope note. Current
state, confirmed by reading every `router.py` and `tests.py` under
`src/vmss_api/*/` before writing this design:

- 9 feature packages, all registered in `api.py`/`main.py`:
  `auth`, `tenant`, `platform`, `org_structure`, `visitors`, `invitations`,
  `registrations`, `reports`, `identity_verification`.
- Existing coverage is already broad (~230 test functions). This is a
  gap-fill and verification pass, not a from-scratch suite.
- Shared test infra: root `conftest.py` (`db_session`, `client`, `tenant`,
  `branch`, `user` w/ `ADMIN_PERMISSION_CODES`, `user_without_permissions`,
  `superadmin`, `make_tenant_schema`, `open_tenant_session`) and root
  `factories.py` (one `polyfactory.SQLAlchemyFactory` per model). No shared
  `_login` helper — each feature's `tests.py` defines its own.
- `ADMIN_PERMISSION_CODES` in root `conftest.py` is a hand-maintained list;
  it must already include every permission code this change's new tests
  exercise, or the shared `user` fixture 403s unexpectedly.

## Goals / Non-Goals

**Goals:**
- One workflow-ordered matrix (below) covering every endpoint across all 9
  packages, so gap-finding is systematic, not another spot-check.
- Every endpoint checked against `testing-standards.md` §2 (happy path,
  permission-denied or its public-auth equivalent, tenant-isolation or its
  documented non-applicability) plus the automation-tester scenarios in the
  matrix's "Extra scenarios" column (validation, conflict/duplicate,
  not-found, rate-limit, idempotency-replay — wherever the endpoint actually
  has that behavior).
- Fix bugs the audit finds, within the stop-and-report threshold defined
  under Decisions.
- End with a green `ddev exec uv run pytest` run and a written record of
  before/after test counts per feature.

**Non-Goals:**
- Not a rewrite of already-passing tests. Don't touch a test that already
  correctly covers its scenario just to restyle it.
- Not a refactor of production code. A fix is scoped to the smallest change
  that makes behavior match its intended contract.
- Not a new capability or a spec-level behavior change — see proposal.md's
  Capabilities section. A finding that would require one is out of scope
  (flagged as a follow-up, see Open Questions).
- Not a performance or load-test pass — `query-performance.md` concerns are
  a separate audit, not this change's job.

## Decisions

### Workflow-ordered test matrix

Endpoints grouped in the order a visitor's lifecycle actually flows through
them, matching `proposal.md`'s 7 stages. "Isolation" = tenant-schema
isolation unless noted; "Extra" = scenarios beyond the §2 bar worth a
tester's attention.

| # | Stage | Endpoint | Auth/Permission | Isolation | Extra scenarios |
|---|---|---|---|---|---|
| 1 | Provisioning | `POST /platform/auth/login` | public, superadmin | global-schema only | rate-limit (5/min), bad credentials |
| 2 | Provisioning | `POST /platform/tenants` | superadmin token | global-schema only | duplicate slug 409, rate-limit (3/min) |
| 3 | Provisioning | `GET /platform/tenants` | superadmin token | global-schema only | tenant-user token rejected (403) |
| 4 | Provisioning | `GET /tenants/me` | `tenants:read` | **document non-applicability** | — |
| 5 | Auth/RBAC | `POST /auth/login` | public | tenant-scoped | rate-limit (5/min), bad credentials |
| 6 | Auth/RBAC | `GET /auth/me` | authenticated only | tenant-scoped | no permission-denied case expected; 401 only |
| 7 | Auth/RBAC | `POST /auth/users` | `users:manage` | tenant-scoped | duplicate email/employee-code conflict |
| 8 | Auth/RBAC | `POST .../branch-roles` | `users:manage` | tenant-scoped | invalid branch id |
| 9 | Auth/RBAC | `DELETE .../branch-roles/{id}` | `users:manage` | tenant-scoped | not-found |
| 10 | Auth/RBAC | `POST /auth/employees/sync` | `employees:manage` | tenant-scoped | unknown-department 404, **duplicate-within-batch 409 across the whole loop, not just final commit** |
| 11 | Auth/RBAC | `GET /auth/employees` | `require_branch_scope` | tenant-scoped | optional `X-Branch-ID` present/absent |
| 12 | Auth/RBAC | `GET /auth/permissions` | `roles:view` | tenant-scoped | — |
| 13 | Auth/RBAC | `POST /auth/roles` | `roles:manage` | tenant-scoped | duplicate role name |
| 14 | Auth/RBAC | `GET /auth/roles`, `/verify`, `/{id}` | `roles:view` | tenant-scoped | pagination, not-found |
| 15 | Auth/RBAC | `PUT`/`DELETE /auth/roles/{id}` | `roles:manage` | tenant-scoped | not-found, role-in-use conflict |
| 16 | Org structure | `/company` CRUD | `companies:manage`/`:view` | tenant-scoped | singleton not-yet-configured 404 vs. exists-200 |
| 17 | Org structure | `/branches` CRUD + `/current` + `/provision` | `branches:*` | tenant-scoped | `/provision`'s multi-entity transaction rollback on partial failure |
| 18 | Org structure | `/buildings`, `/floors`, `/departments` CRUD | branch-scoped perms | tenant-scoped + branch-scoped | cross-branch access denial |
| 19 | Org structure | `/reception-desks`, `/security-gates` CRUD | branch-scoped perms | tenant-scoped + branch-scoped | cross-branch access denial |
| 20 | Visitor-type config | `/visitor-categories` CRUD | `visitor-categories:*` | tenant-scoped | permission-denied on list/get/delete, not just create/update |
| 21 | Visitor-type config | `/approval-workflow-rules` CRUD | `approval-workflow-rules:*` | tenant-scoped | permission-denied on list/get/delete |
| 22 | Invitation intake | `POST /invitations` | `invitations:create` (branch-scoped) | tenant-scoped | multipart file validation ordering (validate-before-persist, no orphaned uploads on reject), idempotency-key replay |
| 23 | Invitation intake | `GET /invitations/track` | public | tenant-scoped (default-tenant assumption, documented) | rate-limit (20/min), not-found |
| 24 | Walk-in intake | `POST /registrations/walk-in` | `X-Device-Key` | tenant-scoped | missing/invalid/inactive device key, disguised-file-type + oversized-file rejection at this router's own boundary, idempotency-key replay |
| 25 | Identity verification | `POST /identity-verification/otp/request` | public | **Redis key-namespace isolation, not Postgres schema** | rate-limit (20/min), idempotency-key |
| 26 | Identity verification | `POST /identity-verification/otp/verify` | public | Redis key-namespace isolation | wrong code, expired code, attempt-exhaustion lockout, no-plaintext-in-logs |
| 27 | Reporting | `GET /reports/branches/rollup` | `reports:view` | tenant-scoped | every rollup field populated (incl. `security_gate_count`, previously untested) |

Rows in **bold-flagged cells** are known gaps from the initial survey; every
other row gets checked against current tests during execution — a row with
full coverage already needs no new test.

### Execution order: baseline → per-stage pass → closing gate

1. Run `ddev exec uv run pytest` once before touching anything; record the
   real pass count. Don't reuse a count from an archived change's proposal —
   confirm fresh, since code has moved since any of those.
2. Walk the matrix stage-by-stage in the order above (not file-by-file
   alphabetically) — this mirrors the actual dependency chain (you can't
   meaningfully test invitations without org structure and auth already
   covered), and matches how an automation tester would exercise the product
   end-to-end.
3. Within a stage, add only the tests the matrix marks missing after
   checking the feature's current `tests.py`.
4. Run the full suite again at the end; report the closing count and confirm
   it only grew, never shrank, from step 1.

### Stop-and-report threshold for bugs found mid-audit

Fix inline, in this change, when the fix is:
- Confined to one service/router function's internal logic.
- Makes behavior match what the endpoint's own docstring/permission/response
  schema already promises (e.g. a 500 that should have been a 409, a
  filesystem write ordering issue) — same class as `close-api-test-coverage-
  gaps`'s two precedent fixes.

Stop and report instead of fixing, if the finding is:
- A missing endpoint entirely (e.g. `invitations:view`/`invitations:cancel`
  permissions exist in the RBAC catalog with no endpoint using them — a known
  pre-existing gap, not new, already flagged as future scope in an archived
  change).
- A case where the "intended" contract is itself ambiguous (no docstring,
  schema, or prior spec settles what *should* happen) — this needs a product
  decision, not a test-driven guess.
- Anything that would require a `Modified Capabilities` entry per
  `proposal.md` (i.e., an actual behavior change visible to API consumers,
  not an internal correctness fix).

### Redis-namespace isolation test for `identity_verification`

Modeled on the existing Postgres tenant-isolation pattern
(`make_tenant_schema`/`open_tenant_session`) but adapted: since OTP state is
Redis-only and keyed by `vmss:{tenant_id}:...`
(`database-architecture.md` §6), the test creates two `Tenant` rows (via
`TenantFactory`, no second Postgres schema needed) and asserts that
requesting/verifying an OTP for tenant A does not affect or leak into tenant
B's Redis keys — using the real Redis instance the rest of the identity-
verification tests already talk to, not a mock.

### `tenant` feature's tenant-isolation non-applicability

Write this down explicitly as a test (or a documented comment plus an
existing-passing assertion), the same way `audit-and-expand-api-test-coverage`
did for `platform`: `TenantRepository` operates on the **global** schema, so
there's no tenant schema for it to leak across. `testing-standards.md` §2's
requirement is satisfied by demonstrating this, not by skipping it silently.

## Risks / Trade-offs

- **Matrix says "existing coverage may already be sufficient" for most
  rows** → risk of under-delivering if the pass is too quick to mark a row
  "already covered." Mitigation: for every row, actually re-read the
  relevant `tests.py` function bodies (not just function names) before
  marking it covered — a test named `test_x_requires_permission` that
  asserts the wrong status code is worse than no test.
- **Bug fixes discovered mid-audit could cascade** (e.g. the employee-sync
  fix touches a loop other code paths call) → mitigation: run the full suite
  after every individual fix, not just once at the very end, so a regression
  is caught next to the change that caused it.
- **`ADMIN_PERMISSION_CODES` drift** (§ Context) → if a new test needs a
  permission code missing from that shared list, add it there rather than
  hand-rolling a bespoke role/user fixture per test — keeps the fixture
  usable for future tests too.
- **Redis-isolation test flakiness**: real Redis state could leak between
  test runs if key expiry/cleanup isn't deterministic → mitigation: reuse
  whatever autouse Redis-reset fixture `identity_verification/tests.py`
  already defines rather than inventing a second one.

## Open Questions

- Should the pre-existing `invitations:view`/`invitations:cancel`
  endpoint-less permissions (flagged by `close-api-test-coverage-gaps` as
  future scope) be built now, or stay deferred? Deferred by default per this
  design's stop-and-report threshold; revisit only if the user asks for it
  explicitly in a follow-up change.
- Three unarchived changes reference features that already look
  fully implemented (`add-pre-registration`, `harden-invitation-tracking-
  fidelity`, `document-invitation-create-payload-shape`) — housekeeping
  (archive or update), not part of this change's task list.
