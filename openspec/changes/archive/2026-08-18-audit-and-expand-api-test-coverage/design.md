## Context

See `proposal.md` - Why for motivation. This covers all 7 feature test suites
(`auth`, `invitations`, `org_structure`, `platform`, `reports`, `tenant`,
`visitors`) totaling 59 endpoints and 168 existing tests, plus 3 concrete gaps
already confirmed during the proposal:

| Gap | Endpoint | Evidence |
|---|---|---|
| 1 | `GET /api/v1/company` | `org_structure/tests.py:493-497` (`test_get_company_not_configured_yet`) and `:511-521` (`test_delete_company_success`) both only assert the 404 path; no test creates a company then asserts `GET` returns it. |
| 2 | `GET /api/v1/branches/{branch_id}` | `org_structure/tests.py:297-306` (`test_delete_branch_success`) is the only test hitting this route, and only to assert 404 post-delete. |
| 3 | `POST /api/v1/platform/tenants` | `platform/tests.py:122` (`test_create_tenant_provisions_real_schema`) calls `platform.service.create_tenant()` directly (documented, deliberate — avoids double-provisioning cost); `platform/tests.py:53` (`test_create_tenant_rate_limit_trips`) is the only HTTP-level test and deliberately only ever hits 409/429 on a reused slug. |

Existing test infrastructure already provides what's needed to close all 3:
`client`/`user`/`tenant`/`branch` fixtures and `_login()` helpers (`conftest.py`,
per-feature `tests.py` preambles), so no new fixture or factory work is needed
for these 3 — they follow the exact pattern already used by e.g.
`test_update_branch_success` (create via fixture, call the route, assert body).

## Goals / Non-Goals

**Goals:**
- Close the 3 confirmed gaps with HTTP-level happy-path tests, each following
  the existing test-file's established pattern (login helper, `client`
  fixture, `success_response` envelope assertions) — no new pattern
  introduced.
- Systematically re-verify every endpoint across all 7 routers has a
  happy-path test (not just the 3 already found), and treat any further gap
  found the same way: add the missing test using existing fixtures/patterns.
- Keep the full suite green throughout — each new test must pass against the
  actual running application, not be written to match an assumed behavior.

**Non-Goals:**
- Not adding tests beyond what `testing-standards.md` §2 requires (happy path
  per endpoint, ≥1 permission-denied, ≥1 tenant-isolation per feature) — e.g.
  not adding exhaustive boundary-value or fuzz tests for every field, which
  would be scope creep beyond "verify scenarios are covered."
  `invitations/tests.py` already has extensive validation-scenario coverage
  (31 tests) beyond this minimum; that's pre-existing and untouched, not a
  template to replicate elsewhere.
- Not writing a new tenant-isolation test for `platform`/`tenant` — as
  established in proposal.md, their repositories operate on global-schema
  tables only; forcing a tenant-isolation test onto them would test nothing
  real and contradict `database-architecture.md` §2's own tier table.
- Not touching production code as a default outcome. If a new or existing
  test reveals a genuine behavioral gap (an endpoint that doesn't actually do
  what its own contract implies), that's flagged and the fix is scoped
  separately — see Risks below — not silently patched inside this
  test-coverage change.

## Decisions

**1. New tests follow each file's existing local convention, not a new shared
helper.**
Alternative considered: extract a shared "assert full CRUD round-trip" helper
usable across `org_structure`'s sub-resources. Rejected — every other
sub-resource (`building`, `floor`, `department`, `desk`, `gate`) already has
its own explicit `test_get_<resource>_success` written in the same direct
style; introducing an abstraction now, for exactly 2 missing cases, would be
exactly the premature-abstraction pattern the last audit flagged as a watch
item elsewhere. Write `test_get_company_success` and `test_get_branch_success`
in the same direct style as their sibling tests.

**2. The systematic re-verification is a checklist pass, not a rewrite.**
For each of the 4 remaining routers (`auth`, `invitations`, `tenant`,
`reports`) and the already-covered sub-resources of `org_structure`
(building/floor/department/desk/gate) and `visitors` (category/workflow_rule):
list every route the router exposes, find the corresponding
`test_<action>_<resource>_success`-shaped test, and confirm it actually
exercises that route (not just shares a name). Where proposal.md's spot-check
already confirmed coverage (reports, tenant, visitors, and 5 of
`org_structure`'s 7 sub-resources), the task is to re-confirm during
implementation, not re-derive from scratch — but re-confirm against the
actual current file, since it may have changed since the proposal's read.

**3. A test that fails because of a real bug stops the task, doesn't get
"fixed" by loosening the assertion.**
If closing gap 1, 2, or 3 (or a newly-found gap) turns up an endpoint that
doesn't actually return what its own contract implies (e.g. `POST
/platform/tenants` doesn't actually return a `TenantSummaryOut`-shaped body,
or `GET /branches/{id}` leaks a soft-deleted row), that's a real product bug
uncovered by finally testing the happy path — not a reason to write a looser
assertion so the new test passes. Per the apply workflow's own guardrails,
this pauses implementation and reports the finding rather than silently
patching production code as a side effect of a test-coverage change.

**4. Test data via existing fixtures/factories, not new hand-built dicts.**
Per `testing-standards.md` §1, any new row a new test needs goes through the
project's existing fixtures (`conftest.py`'s `user`/`tenant`/`branch`) or
`factories.py`'s `polyfactory`-based factories — consistent with how every
existing test in these files already builds its data.

## Risks / Trade-offs

- [Risk] Gap 3's new test actually provisions a tenant schema via the real
  HTTP endpoint (unlike the existing service-level test, which already does
  the same thing and documents why it's safe) — adds real schema-creation +
  Alembic-migration cost to the suite's runtime → Mitigation: follow
  `test_create_tenant_provisions_real_schema`'s own pattern of dropping the
  schema it creates in a `finally`/teardown block, so the new test doesn't
  leave permanent schema bloat in `vmss_test` across runs.
- [Risk] The systematic checklist pass (Decision 2) could itself surface more
  gaps than the 3 already confirmed, expanding scope mid-implementation →
  Mitigation: this is expected and is exactly what "check all scenarios"
  was asked for; each additional gap found gets the same treatment as gaps
  1-3 (add the missing test using existing patterns), reported as it's found
  rather than silently bundled in without visibility.
- [Risk] Fixing gap 1/2's missing happy-path test could reveal that
  `get_company`/`get_branch` never actually worked correctly for some edge
  case (e.g. wrong-branch access) → Mitigation: Decision 3 — stop and report,
  don't silently patch.

## Migration Plan

1. Re-run the full suite (already done once during this proposal: 186
   passed) as the starting confirmation baseline for implementation.
2. Add the 3 confirmed-gap tests (company GET, branch GET, tenant-create
   POST), one at a time, running just that feature's `tests.py` after each
   addition.
3. Run the systematic checklist pass (Decision 2) across the remaining
   routers/sub-resources; add any further test found missing, same
   one-at-a-time verification.
4. Full `ddev exec uv run pytest` as the final gate; report the new total
   (expected ≥189).

**Rollback**: every change here is additive (new test functions) with no
production-code edits expected — reverting is deleting the added test
function(s) if one turns out to be flawed. No data migration, no deployment
step involved.

## Open Questions

None — Decision 3 already resolves how to handle the one real unknown (does
a "happy path" test reveal a genuine bug), and the systematic pass's scope is
fully bounded by `testing-standards.md` §2's existing, already-adopted
requirement rather than a new invented standard.
