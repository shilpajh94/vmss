## Context

See `proposal.md` — Why for the merge history and motivation. This design
extends `openspec/changes/archive/2026-08-21-complete-api-test-coverage/
design.md`'s workflow-ordered matrix (stages 1-7) and
`verify-sso-and-full-api-suite/design.md`'s Stage 8 (SSO) with the two
things neither prior pass could have checked, because the merged tree
didn't exist yet when they were written:

- **Current baseline, confirmed before writing this design**:
  `ddev exec uv run pytest` → **493 passed**; `ruff check .` → all checks
  passed; `ruff format --check .` → 373 files already formatted. Up from
  `verify-sso-and-full-api-suite`'s closing count of 358, because that
  audit's tree didn't yet contain `harden-referential-integrity-and-rbac-
  gates`, `codebase-review-and-e2e-scenario-test`, or
  `protect-walkin-default-branch-config`'s own test additions — those
  landed on `feature/code-refactoring` independently and are only now
  combined with SSO by this merge.
- **Confirmed interaction points** (read `auth/service.py`, `sso/service.py`,
  `sso/models.py`, `org_structure/service.py::delete_branch`,
  `tests/test_workflow_full_lifecycle.py` before writing this design):
  - `separate-admin-staff-login` added a shared `has_admin_role(user)`
    helper in `auth/service.py`, called from both
    `authenticate_user` (password login → 403) and `sso/service.py`'s
    callback handler (existing-account match → generic login failure).
    `SsoRoleMapping.role_id` is a plain FK to `roles.id` — nothing in the
    merged schema stops an admin from creating a role mapping targeting a
    role named `admin` today except `sso/service.py::create_role_mapping`'s
    own guard (confirmed present, mirroring the `visitor`-target guard
    noted in that change's own Context).
  - `harden-referential-integrity-and-rbac-gates` established the pattern
    of translating a check-then-act race into a clean 409 (duplicate branch-
    role grant in `assign_branch_role`) rather than an unhandled 500, and
    `codebase-review-and-e2e-scenario-test` applied the same pattern to
    `invitations/service.py::approve_invitation`'s concurrent-approval race.
    Reading `sso/service.py::_provision_or_resolve_user` against that
    pattern surfaces the same class of gap, not yet closed here: it checks
    `UserRepository.get_by_email(email)` for `None`, then calls
    `auth_service.create_user(...)` (which does a bare `tenant_db.add(user)`
    + `flush()`, no `IntegrityError` handling) for a **new** email — two
    concurrent first-time SSO logins for the same not-yet-provisioned email
    (e.g. a double-click on "Sign in with SSO," or an IdP redirect retry)
    can both pass the `None` check before either commits, and the second
    hits `User.email`'s unique constraint (`auth/models.py:75`) as a raw
    `IntegrityError`, surfacing as an unhandled 500 instead of this
    codebase's own established "concurrent duplicate creation is a 409"
    contract.
  - `protect-walkin-default-branch-config` added a third guard to
    `org_structure/service.py::delete_branch` (reject if
    `branch.code == settings.registration_default_branch_code`).
    `tests/test_workflow_full_lifecycle.py` (from
    `codebase-review-and-e2e-scenario-test`) exercises deleting its
    second, purpose-created branch at the end of the workflow — that
    branch's `code` is developer-chosen test data, not
    `conftest.py`'s shared `branch` fixture (`code="MAIN"`) that the walk-in
    guard's own design doc flagged as the collision risk, but this pass
    confirms that a fresh read, not an assumption carried over from that
    design doc.

## Goals / Non-Goals

**Goals:**
- Confirm the full, currently-green 493-test suite still passes as one
  designed set of scenarios, not just as accumulated file-by-file luck —
  by walking the workflow-ordered matrix stage by stage, same as every
  prior audit in this series.
- Specifically exercise the three interaction seams above, since they are
  the concrete, code-verified (not hypothetical) points where two
  independently-shipped changes touch the same table or code path.
- Confirm every `#### Scenario:` in `add-sso-oidc-login`'s un-synced delta
  specs (`specs/auth`, `specs/rate-limiting`, `specs/sso-authentication`)
  still maps to a passing test on this branch.
- Fix any real gap found, end with a clean `pytest`/`ruff`/`mypy` gate.

**Non-Goals:**
- Not re-deriving stages 1-7's or Stage 8's full per-row matrix from
  scratch — both prior audits' tables stand; this pass re-runs them and
  spot-confirms their previously-named regression tests still exist and
  pass (same "spot-check, backed by the full suite as the real safety net"
  posture `verify-sso-and-full-api-suite/design.md` used for its own
  stages 1-7).
- Not the four manual live-IdP steps (out of reach in this environment,
  already flagged elsewhere).
- Not archiving any of the now-superseded change folders — a separate,
  later action once this pass confirms the merge is solid.
- Not resolving any genuine contract conflict between two changes, if one
  is found — that gets stopped-and-reported per proposal.md's threshold,
  not decided unilaterally here.

## Decisions

### Interaction check 1 — SSO role-mapping vs. the admin/staff login gate

Add a test that creates an `SsoRoleMapping` targeting a mapped role, then
directly asserts `create_role_mapping` still rejects a mapping whose target
role name is `admin` (case-insensitive) post-merge — i.e. re-confirm
`separate-admin-staff-login`'s guard is the thing actually preventing this,
not an accident of `sso/service.py`'s specific test fixtures. Separately,
add a callback-flow test: an existing user account already holding Admin
(via ordinary `UserBranchRole` grant, not SSO) attempts SSO login — confirm
`has_admin_role`'s callback-side check rejects it, exercising the exact
interaction the merge combined (SSO callback code path + the shared helper
`separate-admin-staff-login` introduced) rather than trusting each
change's own isolated tests still add up correctly.

### Interaction check 2 — concurrent first-time SSO provisioning vs. the check-then-act-race pattern

Add a test simulating two interleaved `_provision_or_resolve_user` calls
for the same brand-new email (same shape as the existing
`approve_invitation` concurrency test noted in `codebase-review-and-e2e-
scenario-test/design.md` — simulate the interleaving, not a real thread
race), confirming the current behavior surfaces the raw `IntegrityError`
as an unhandled 500. This is a genuine, previously-undetected gap — not
something either contributing change's own test suite could have caught,
since `add-sso-oidc-login`'s tests never provision concurrently and
`harden-referential-integrity-and-rbac-gates`/`codebase-review-and-e2e-
scenario-test` never touch `sso/`. Fix inline, confined to
`sso/service.py::_provision_or_resolve_user`: catch `IntegrityError` around
the create-user commit and re-resolve by email (the second racer's intent —
"log this email in" — is still satisfiable by returning the row the first
racer just created), the same "reload and treat the constraint as the
already-current state" shape `assign_branch_role`'s 409 fix uses, adapted
here to a login flow where failing the second request outright would be a
worse user experience than a login endpoint 500ing on a double-click.

### Interaction check 3 — full-lifecycle branch deletion vs. the default-branch-code guard

Re-run `test_workflow_full_lifecycle.py` and confirm its branch-deletion
step still succeeds; additionally confirm (by inspecting the test's branch
creation payload, and adding an assertion if none exists) that the branch
it deletes does not incidentally share `settings.registration_default_
branch_code`'s value — if it does, that is the same test-data-coincidence
risk `protect-walkin-default-branch-config/design.md` already named for
`conftest.py`'s shared fixture, just recurring in a second test file, and
gets fixed by giving that test's second branch an explicit, clearly
non-default code rather than an implicit one.

### Re-confirming stages 1-8 without re-deriving either matrix

Run the full suite; for each of the 8 prior stages, spot-check that the
specific regression tests already named by the two prior audits still
exist and pass: the four named in `complete-api-test-coverage`'s
carry-forward list, plus SSO's `test_sso_provider_is_tenant_isolated` /
`test_sso_role_mapping_is_tenant_isolated` split and
`test_logout_writes_audit_entry` from `verify-sso-and-full-api-suite`. If
the full suite is green and all of those still pass individually, stages
1-8 are confirmed without re-writing their matrices.

## Risks / Trade-offs

- **Interaction checks 1-2 could find nothing wrong** (both guards may
  already correctly cover the shared code paths) → not wasted effort: a
  passing new test is the actual proof the merge didn't quietly break the
  seam, which no existing test asserts today since neither change's own
  suite exercises the other change's code.
- **Interaction check 2 could find that `_provision_or_resolve_user`
  legitimately needs its own insert semantics** (e.g. "SSO re-login should
  silently no-op on an existing identical grant, not 409") rather than a
  bug → mitigation: if the intended contract is genuinely ambiguous, this
  is stopped-and-reported per proposal.md's threshold, not silently forced
  to match `assign_branch_role`'s behavior.
- **Spot-check approach for stages 1-8 could miss a genuine regression**
  the previously-named tests don't happen to cover → mitigation: same as
  both prior audits — the full 493-test suite run is the actual safety
  net; the spot-check is an additional targeted look at the
  highest-risk-of-regression items, not the only check.

## Open Questions

None — the interaction seams to check were identified by reading the
actual merged code (not guessed), and every check above has a concrete
pass/fail outcome that either confirms the guard holds or produces a
stop-and-report finding per the established threshold.
