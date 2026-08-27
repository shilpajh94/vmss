## Why

Three changes were just archived in this session
(`2026-08-27-visit-info-lookup-api`, `2026-08-27-fix-visit-info-lookup-access`,
`2026-08-27-verify-api-regression-suite`), and `verify-api-regression-suite`
already confirmed the full test suite is green (393/393) and a live-request
pass over every feature area succeeds. That change verified *that things
still run*; it did not do a line-level code review of what changed, and it
did not check whether each feature's test suite actually satisfies
`testing-standards.md` §2 (happy path per endpoint, a permission-denied
case, a tenant-isolation case) or covers every scenario each capability's
own spec under `openspec/specs/` commits to. The user has now asked for
exactly that: a code review for latent breakage, and an audit of whether
the test suite is proper and fully satisfies the documented requirements —
not just "does it currently pass."

## What Changes

- **Code review** of this session's actual code changes (the still-
  uncommitted diff touching `registrations/deps.py`, `visit_info/router.py`,
  `visit_info/service.py`, `auth/repository.py`, and their tests) for
  correctness bugs, edge cases, and reuse/simplification issues — using the
  project's `code-review` process, not a re-read of the same manual
  verification already done during apply.
- **Test-coverage audit**, per feature package with a `tests.py`
  (`auth`, `core`, `identity_verification`, `invitations`, `org_structure`,
  `platform`, `registrations`, `reports`, `tenant`, `visit_info`,
  `visitors`): confirm each endpoint has a happy-path test, each
  permission-gated endpoint has a permission-denied test, and each
  tenant-scoped repository has a tenant-isolation test, per
  `testing-standards.md` §2's stated minimum.
- **Spec-to-test cross-check**, per capability under `openspec/specs/`
  (14 capabilities): confirm every `#### Scenario:` in a capability's main
  spec maps to an identifiable test, and flag any spec'd behavior with no
  corresponding test (or any test asserting behavior the spec doesn't
  document, which usually means one of the two is stale).
- If either pass finds a genuine gap or bug, fix it (smallest correct
  change: a missing test, a real bug, or a stale spec line) and re-verify —
  same "decide the exact fix when something is actually found, not now"
  posture as `verify-api-regression-suite`.
- **Out of scope, flagged not silently skipped**: the `sso` feature. Its
  source exists only on the unmerged `feature/sso-api-task` branch (real,
  committed work — confirmed via `git log --all`), not on this branch
  (`bug-fix/api-tasks`, forked from `development`). `src/vmss_api/sso/`
  here contains only stale `__pycache__` bytecode from an earlier branch
  checkout, no source, and `api.py` doesn't mount an `sso` router — so
  there is no `sso` code or requirement to review or test on this branch
  today.
- `skip_specs: true` — this is a review/audit pass. Any bug fix it produces
  restores documented, already-specified behavior (or adds a missing test
  for behavior the spec already commits to); it does not introduce a new
  requirement, so no spec delta is expected.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — see "Why nothing above needs a spec delta.")

## Impact

- **Code**: none planned up front. Any fix arising from a discovered issue
  is scoped to the specific file(s) at that time.
- **Tests**: may gain new test cases where the audit finds a genuine
  coverage gap against `testing-standards.md` §2 or an unspec'd-but-tested/
  spec'd-but-untested scenario.
- **Scope**: 11 feature packages with `tests.py`, cross-checked against 14
  capability specs under `openspec/specs/`. `sso` explicitly excluded (see
  Why).
