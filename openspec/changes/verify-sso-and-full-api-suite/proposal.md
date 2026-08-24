## Why

API-19 (staff OIDC SSO, `add-sso-oidc-login`) just landed as the newest,
largest, and most security-sensitive feature in this codebase — external
token verification, a new encryption primitive, and a brand-new public
attack surface (login-initiate/callback/exchange) — and it has not yet been
through the same systematic, workflow-ordered verification pass this
project already ran once before for API-01 through API-15
(`complete-api-test-coverage`, archived 2026-08-21). The user wants
confidence that (a) SSO login genuinely works end to end, and (b) nothing
about adding it regressed or left a gap anywhere in the other 18 APIs,
before committing the working tree (SSO plus whatever this audit fixes) as
one reviewed unit.

**Scope note on "all 19 APIs":** per this project's existing informal
`API-01`..`API-19` backlog numbering (confirmed via `git log`, prior audit
proposals, and inline `API-0N` markers across the codebase), `API-16`,
`API-17`, and `API-18` were never assigned to anything — there is no
reference to them anywhere in `docs/`, `openspec/`, or `Requirements/`. This
proposal covers the 16 numbers that do map to real, built work (API-01
through API-15, already re-verified once in `complete-api-test-coverage`,
plus API-19 now), re-running the full workflow-ordered pass rather than
assuming the prior audit's findings still hold, since code has moved since
then (most notably: `auth/router.py`'s login rate limit changed from
5/minute to 3/minute, and `auth/rbac_catalog.py` gained two new permission
codes, both as part of shipping SSO).

## What Changes

- Extend `complete-api-test-coverage`'s workflow-ordered test matrix
  (`design.md`) with an eighth stage — SSO login — positioned right after
  Auth/RBAC (the stage it extends) and before Org structure, matching where
  it sits in an actual staff sign-in flow. Every endpoint from the original
  7 stages is re-walked too, not skipped, since this is a fresh pass, not a
  diff against the old one.
- Re-run the full existing suite first to get a real, current baseline (345
  tests as of this proposal — includes SSO's own 26), then systematically
  compare it against the full 8-stage matrix, exactly as
  `complete-api-test-coverage` did: happy path, permission-denied (or its
  public-auth equivalent), tenant-isolation (or its documented
  non-applicability), plus validation/conflict/not-found/rate-limit/
  idempotency scenarios wherever the endpoint has that behavior.
- For the new SSO stage specifically, verify beyond what API-19's own
  `add-sso-oidc-login` change already tested: that the login flow survives
  the two most likely real-world failure modes not exercised by that
  change's own test suite — the encryption key rotating/missing mid-flight,
  and a second tenant's SSO config never being reachable from the first
  tenant's login attempt (a stronger, HTTP-level version of the repository-
  level tenant-isolation test that change already has).
- Fix any bug the audit finds, using the same stop-and-report threshold
  `complete-api-test-coverage` established (fix inline if confined to one
  service/router function and makes behavior match its own documented/
  intended contract; stop and report if it's a missing endpoint, an
  ambiguous "intended" contract, or anything that would require a
  `Modified Capabilities` entry).
- End with a green `ddev exec uv run pytest`, `ruff check`, `ruff format
  --check`, and `mypy` (on `core`/`auth`/`sso`) run, and a closing summary
  the user can review before committing.
- **Not in scope**: the four manual, live-IdP verification steps
  `add-sso-oidc-login/tasks.md` §11 already flags as requiring a real
  browser and the out-of-band Microsoft Entra ID credentials — this audit
  covers everything testable in CI/locally without them. Archiving
  `add-sso-oidc-login` itself (syncing its delta specs into
  `openspec/specs/`) is also a separate, later action — this change only
  verifies the code is solid enough to be worth archiving.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None planned. Adding tests for scenarios already part of each endpoint's
existing, intended contract is not a spec-level behavior change. Fixing a
bug so an endpoint matches its already-documented/intended contract is the
same class of fix `complete-api-test-coverage` made without a capability
delta. If the audit surfaces a case where the *intended* contract itself is
ambiguous or needs to change, that is out of scope for this change and gets
flagged as a follow-up in the closing summary, not folded in silently. This
change sets `skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **Affected code**: potentially every feature's `tests.py` (`auth`,
  `tenant`, `platform`, `org_structure`, `visitors`, `invitations`,
  `registrations`, `reports`, `identity_verification`, `sso`) plus
  `tests/test_api_documentation.py` — exact files depend on what the pass
  finds missing.
- **Possible production-code fixes**: only if the audit finds a real bug,
  scoped to the specific service/router file involved — not a refactor
  pass.
- **No dependency, schema, or migration changes** beyond what
  `add-sso-oidc-login` already introduced.
- **No breaking changes.**
