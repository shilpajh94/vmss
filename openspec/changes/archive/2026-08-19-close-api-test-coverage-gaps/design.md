## Context

Test coverage across `auth`, `org_structure`, `visitors`, `platform`, `core`, `invitations`,
`registrations`, and `reports` was audited against `testing-standards.md` §2 and the
requirements in `openspec/specs/rate-limiting/spec.md` / `openspec/specs/api-documentation/
spec.md`. The suite already exceeds the §2 minimum in most modules (`org_structure` and
`invitations` in particular). The gaps below are the ones the audit actually found — this
design does not propose a wholesale rewrite of test files that already pass.

One structural fact shapes where new tests go: `src/vmss_api/core/tests.py` currently tests
only `core/storage.py` (file upload, API-14) despite its name suggesting it covers all of
`core/` — rate limiting and OpenAPI/versioning (API-08) are instead covered by the
root-level `tests/test_api_documentation.py`. New API-08 assertions belong there, not in
`core/tests.py`, to stay consistent with where that concern already lives.

## Goals / Non-Goals

**Goals:**
- Close every concrete coverage gap identified in the audit (see `proposal.md` - What
  Changes), using the existing factory/fixture infrastructure (`factories.py`,
  `conftest.py`) — no new test infrastructure is needed.
- Fix the one real bug found (orphaned ID-proof uploads on a rejected group invitation) with
  the smallest change that satisfies the new spec scenario: validate before persisting.

**Non-Goals:**
- Not re-testing behavior already covered (e.g. `org_structure`'s 36 endpoints, or
  `invitations`' existing 29 tests) — this is a gap-closing change, not a rewrite.
- Not building the `invitations` list/cancel endpoints implied by the currently-unenforced
  `invitations:view`/`invitations:cancel` permission codes — that is new feature scope, not
  a test or bug fix (see proposal.md's "Explicitly out of scope").
- Not archiving or updating the three unarchived invitation-related changes the audit found
  to be stale/already-implemented — flagged for the user to handle separately via
  `opsx:archive`/`opsx:update`.
- Not touching `registrations/deps.py`'s O(n) device-key lookup — a documented, deliberate
  tradeoff, not a defect.

## Decisions

**1. Fix location for the orphaned-upload bug: reorder validation ahead of storage writes,
not add compensating cleanup.** `create_invitation` currently does
validate-then-store-per-visitor inside one loop. Two fixes were considered:
   - *(chosen)* Split into two passes: validate every visitor's file content/type first
     (no I/O), then persist all files only after every one has passed. If any fails, nothing
     has been written yet.
   - *(rejected)* Keep the interleaved loop and add a try/except that deletes
     already-uploaded files if a later visitor fails. Rejected because it's strictly more
     code for the same outcome, and it still does unnecessary storage I/O (upload, then
     immediately delete) on the failure path instead of not doing it at all.

**2. Where the rate-limit envelope test lives: `tests/test_api_documentation.py`, not a new
file.** That file already owns cross-cutting API-08 assertions (OpenAPI metadata, bearer
security, camelCase rendering) and already has the pattern for flipping `limiter.enabled` on
per `core/rate_limit.py`'s test-environment default. Adding it there keeps API-08's
assertions in one place rather than splitting them between two files. The specific endpoint
to trip is `GET /invitations/track` (already has a rate-limit test to model against) — the
new test additionally asserts on the JSON body (`success: false`, non-empty `message`)
where the existing test only asserts `status_code == 429`.

**3. Platform duplicate-slug test: a dedicated test, not a rewrite of the existing rate-limit
test.** `test_create_tenant_rate_limit_trips` stays as-is (it's a valid rate-limit test); a
new `test_create_tenant_duplicate_slug_returns_409` calls the endpoint twice with the same
slug with the limiter left disabled (test-environment default), asserting the second call is
unambiguously 409.

**4. No spec delta for anything except `invitations`.** Every other item in this change adds
a test proving behavior the relevant spec already requires (rate-limiting spec.md's 429
envelope requirement, testing-standards.md's permission-denied/tenant-isolation bar for
visitors) — no requirement's text changes. Only the invitations fix changes actual behavior
(validation ordering), so it's the only capability with a spec delta.

## Risks / Trade-offs

- [The `invitations` capability has no main spec yet — `openspec/specs/invitations/` doesn't
  exist because the changes that would create it (`add-pre-registration` and its two
  follow-ups) are still unarchived.] → This change's delta was written as MODIFIED against
  the requirement text currently living in `add-pre-registration`'s delta (the closest thing
  to a source of truth today) and validates cleanly (`openspec validate` confirms). If those
  three changes are archived before this one, re-run `openspec validate` on this change to
  confirm the delta still applies cleanly against the newly-created main spec.
- [Splitting validate/persist into two passes in `create_invitation` changes the order of
  operations in a function other tests already exercise.] → Mitigated by the existing
  `invitations/tests.py` suite (29 tests) staying green as the acceptance bar — no test
  should need to change its assertions, only the new orphaned-upload regression test is
  additive.

## Migration Plan

No schema, config, or dependency changes. This is test-file additions plus one internal
reordering in `invitations/service.py`. Deploy as a normal PR: `pytest` full suite green,
`ruff`/`mypy` clean, per `git-workflow.md` §3-4. No rollback beyond a normal revert.
