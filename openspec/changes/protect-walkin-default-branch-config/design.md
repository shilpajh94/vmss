## Context

See `proposal.md` for the root cause and why `harden-referential-integrity-
and-rbac-gates`'s guard doesn't cover this case. Relevant existing code:

- `settings.registration_default_branch_code` (`core/config.py`) is a plain
  string setting, read today only by
  `registrations/deps.py::_resolve_default_device_context`. `settings` is
  already the sanctioned single access point for config
  (`database-architecture.md` §8) — no new config-reading mechanism is
  needed, just a new call site.
- `org_structure/service.py::delete_branch` already has two guard checks
  (active org-chart descendants, active device key) that raise
  `HTTPException(409, ...)` before the soft-delete — this is a third check
  of the same shape.
- `org_structure/service.py::update_branch` has **no** guard at all today —
  a blind `setattr` loop over whatever fields the payload sets.
- **Test-data collision, discovered while scoping this change**:
  `conftest.py`'s shared `branch` fixture is built with `code="MAIN"` —
  the exact same string as `settings.registration_default_branch_code`'s
  default. This is coincidental (both independently chose an obvious
  placeholder name), not a deliberate existing test invariant, but it means
  every existing test that deletes or renames that fixture's code would
  start hitting the new guard and failing, purely by accident of shared
  test data. Four existing tests in `org_structure/tests.py` do this today:
  `test_delete_branch_success`, `test_delete_branch_with_inactive_device_key_succeeds`,
  `test_delete_branch_succeeds_after_active_children_soft_deleted`, and
  `test_create_branch_after_soft_delete_reuses_code`.

## Goals / Non-Goals

**Goals:**
- Close the gap: make it structurally impossible to delete or rename-away
  the branch the no-device-key walk-in fallback depends on, mirroring the
  existing guard's "block, don't cascade" posture.
- Keep every existing test's *intent* passing — none of the four tests
  above are about the walk-in default; they're incidentally affected by a
  test-data coincidence, not something this change should weaken the new
  guard to accommodate.

**Non-Goals:**
- Not changing `settings.registration_default_branch_code` itself, its
  default value, or `.env`/`.env.example` — this change only protects
  whatever branch currently matches it.
- Not adding a way to change the configured default branch code from
  within the API (it's a deployment-level setting, changed via `.env` +
  redeploy, same as today) — this change only gates the *branch* side of
  that dependency, not the *config* side.
- Not touching `registrations/deps.py` — its behavior once the
  misconfiguration exists is already correct and already spec'd
  (`registrations/spec.md`'s "Unconfigured default tenant/branch" scenario);
  this change only prevents reaching that state via the ordinary
  delete/rename endpoints.

## Decisions

**Check `branch.code == settings.registration_default_branch_code` as a
third `delete_branch` guard.** Exact string equality, no case-folding —
consistent with `BranchRepository.get_by_code`'s own exact-match lookup,
the only other place a branch code is compared against this setting today.
Alternative considered: compare via a repository method (`BranchRepository
.is_registration_default(branch_id)`) instead of a plain field comparison
in the service. Rejected as unnecessary indirection — no query is needed,
`branch.code` is already an in-memory attribute on the object this
function already has loaded.

**No `update_branch` guard — confirmed unreachable, not just unlikely.**
The original plan (this design doc's first draft, and `proposal.md`'s
initial "What Changes") called for a second guard in `update_branch`
blocking a `code` rename away from the configured default. Before writing
it, `org_structure/schemas.py::BranchUpdate` was checked for its actual
field list: it has no `code` field at all. Pydantic silently drops an
unknown key from a request body rather than erroring or applying it (no
`extra="forbid"` on `CamelModel`), so `PUT /branches/{id}` can never change
a branch's `code` today — confirmed with a test
(`test_update_branch_ignores_code_field`) that sends `code` in the body and
asserts it has no effect, rather than trusting the schema read alone. No
guard was added to `update_branch`: per this codebase's "don't add
validation for a scenario that can't happen" convention, a check for a
condition with no reachable trigger is dead code, not defense-in-depth.
If `code` is ever added to `BranchUpdate` in a future change, that change
is the right place to add this guard alongside it — not before.

**Fix the test-data collision with a module-level `monkeypatch` of
`settings.registration_default_branch_code`, not by changing the shared
`branch` fixture.** `org_structure/tests.py` already has exactly this
pattern for an unrelated setting
(`_default_tenant_slug_matches_test_tenant`, an autouse fixture). Adding a
sibling autouse fixture that monkeypatches
`registration_default_branch_code` to a value no fixture in this file ever
uses (e.g. `"NOT-THE-REGISTRATION-DEFAULT"`) makes the new guard inert for
every test in the file *except* the ones this change adds specifically to
exercise it (which locally monkeypatch the setting back to `branch.code`
for that one test). Alternative considered: change the shared `branch`
fixture's `code` to something other than `"MAIN"`. Rejected — that fixture
is used by dozens of tests across multiple files for unrelated purposes;
touching it has a much larger, harder-to-fully-verify blast radius than a
single new autouse fixture scoped to the one file that actually
deletes/renames it.

## Risks / Trade-offs

- [Risk] The module-level autouse monkeypatch in `org_structure/tests.py`
  could mask a real bug if some *other*, not-yet-written test in that file
  ever needs the real default-code behavior without realizing it's been
  patched away. → Mitigation: the fixture's docstring states exactly what
  it does and why (mirroring `_default_tenant_slug_matches_test_tenant`'s
  own docstring style), and the two new tests that need the real
  collision explicitly re-monkeypatch the setting to `branch.code` locally,
  making the override visible at the call site that matters.
- [Risk] A future change adds a `code` field to `BranchUpdate` without
  anyone remembering this change's finding that renaming needs the same
  guard `delete_branch` has. → Mitigation: `update_branch`'s docstring
  states explicitly why no guard exists there today (no `code` field to
  guard), so a future author adding that field is pointed at the gap by
  the docstring they're editing, not left to rediscover it independently.

## Migration Plan

No data migration; pure code + test change. Deploys as a normal release —
the two guard checks only change behavior for a delete/rename request
against whichever branch happens to match the current
`REGISTRATION_DEFAULT_BRANCH_CODE` value, previously silently allowed.
Rollback is a plain revert.
