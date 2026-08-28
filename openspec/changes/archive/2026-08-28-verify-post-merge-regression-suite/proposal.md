## Why

`feature/code-refactoring` just merged `development` in (merge commit
`98bc8a8`, carrying `246db67`'s earlier merge of development tip `e8de6a5`,
"Merged PR 1615: SSO Login"). That merge is what brought the `sso` feature
package onto this branch for the first time — confirmed via
`git diff --stat 57bd882 e8de6a5`, which shows `src/vmss_api/sso/` (models,
repository, router, service, oidc_client, 1100+ test lines) appearing only
on the development side, alongside real changes to `auth/`, `core/config.py`,
`core/encryption.py`, `core/security.py`, `core/tenancy.py`, `main.py`, and
`invitations/`. At the same time, `feature/code-refactoring`'s own recent
history independently landed `harden-referential-integrity-and-rbac-gates`,
`codebase-review-and-e2e-scenario-test` (the chained
`tests/test_workflow_full_lifecycle.py`), `protect-walkin-default-branch-config`,
and `separate-admin-staff-login` — each verified and merged on its own,
against its own predecessor state, never against a tree that also contains
SSO. This is the first point in this project's history where all of that
exists together in one working tree, and the user has asked to re-test
everything from the beginning rather than assume the pieces still cooperate
just because each one passed in isolation.

A fresh `ddev exec uv run pytest` on the current merged tree already passes
in full — **493 passed**, `ruff check`/`ruff format --check` clean — so this
is not a "something is visibly broken" situation. The risk this change
targets is narrower and easy to miss precisely because the suite is green:
a merge can combine two independently-correct, independently-tested changes
whose *interaction* was never exercised by either change's own tests (e.g.
does SSO-issued login still route through `separate-admin-staff-login`'s
gate correctly; does a role a user holds via an SSO role-mapping interact
correctly with `harden-referential-integrity-and-rbac-gates`'s duplicate-
grant 409 guard; does the new e2e lifecycle test's branch-deletion flow still
respect `protect-walkin-default-branch-config`'s guard now that SSO's own
config/role-mapping tables also reference `branches`/`roles`). None of the
prior, per-change proposals tested against this combined state, because it
didn't exist yet when they were written.

## What Changes

- **Full workflow-ordered re-verification pass** over the current merged
  tree, extending the existing `complete-api-test-coverage` →
  `verify-sso-and-full-api-suite` methodology (workflow-ordered stages,
  each row checked for happy path, permission-denied or its public-auth
  equivalent, tenant-isolation or its documented non-applicability, plus
  validation/conflict/not-found/rate-limit/idempotency where applicable) —
  re-walked fresh against the merged state rather than assumed still valid,
  per every capability/feature that owns a `tests.py`: `auth` (incl. SSO
  login/logout), `sso`, `tenant`, `platform`, `org_structure`, `visitors`,
  `invitations`, `registrations`, `identity_verification`, `reports`,
  `visit_info`, `core`, plus the cross-cutting suites in `tests/`
  (`test_api_documentation.py`, `test_health_readiness.py`,
  `test_workflow_staff_admin.py`, `test_workflow_visitor.py`,
  `test_workflow_full_lifecycle.py`).
- **Cross-change interaction check**, the part genuinely new versus prior
  audits: specifically probe the seams between changes that were each
  verified independently but never together — SSO login/role-mapping
  outcomes against `separate-admin-staff-login`'s admin/staff gate, SSO
  role-mapping-assigned roles (`sso_role_mappings.role_id` → `roles.id`)
  against the branch-role-grant 409 guard from
  `harden-referential-integrity-and-rbac-gates`, and the full-lifecycle
  workflow test's branch-deletion step against
  `protect-walkin-default-branch-config`'s default-branch-code guard, now
  that both exist in the same merged tree.
- **Spec-to-test cross-check** for the SSO capability specifically, since
  `add-sso-oidc-login`'s delta specs (`specs/auth`, `specs/rate-limiting`,
  `specs/sso-authentication`) have not yet been synced into
  `openspec/specs/` (that sync is intentionally a separate, later action) —
  confirm every `#### Scenario:` in those delta specs still maps to a
  passing test in the merged tree, not just in the branch they were
  authored on.
- Fix any bug the pass finds, using the same stop-and-report threshold
  every prior audit in this series established: fix inline if confined to
  one service/router function and it makes behavior match its own
  documented/intended contract; stop and report if it's a missing endpoint,
  an ambiguous "intended" contract, or anything that would require a
  `Modified Capabilities` entry.
- End with a green `ddev exec uv run pytest`, `ruff check`, `ruff format
  --check`, and `mypy` (on `core`, `auth`, `sso` — this project's
  strict-typing scope) run, and a closing summary the user can review
  before committing the merge.
- **Not in scope**: the four manual, live-IdP verification steps
  `add-sso-oidc-login/tasks.md` §11 already flags as requiring a real
  browser and out-of-band Microsoft Entra ID credentials. Archiving any of
  the now-superseded-by-merge changes (`add-sso-oidc-login`,
  `verify-sso-and-full-api-suite`, etc.) is also a separate, later action —
  this change only verifies the merged code is solid.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None planned. This is a verification pass over already-documented/intended
behavior; fixing a bug so the merged code matches each capability's own
existing contract is not a spec-level change, matching every prior change
in this series (`verify-sso-and-full-api-suite`, `codebase-review-and-e2e-
scenario-test`). If the pass surfaces a case where two changes' *intended*
contracts genuinely conflict (not just an untested interaction), that is
out of scope for this change and gets flagged as a follow-up in the closing
summary rather than folded in silently. This change sets `skip_specs: true`
in `.openspec.yaml` accordingly.

## Impact

- **Affected code**: potentially any feature's `tests.py` plus the
  cross-cutting files in `tests/` — exact files depend on what the pass
  finds missing or broken at the interaction seams described above.
- **Possible production-code fixes**: only if the pass finds a real bug,
  scoped to the specific service/router file involved — not a refactor
  pass, and not a re-litigation of any decision the prior, already-merged
  changes already made.
- **No dependency, schema, or migration changes** beyond what the
  development merge already introduced.
- **No breaking changes.**
