## Why

The user asked to test every API against the 10-stage workflow shown in
their screenshot (Platform → Auth & RBAC → Tenant profile → Org structure
→ Visitor categories → Invitations → Walk-in registration → Kiosk lookups →
OTP verification → Reports), confirm no integration gaps remain, and
provision the database with realistic, non-hardcoded sample data across
that whole journey for manual API-client (Swagger/Postman/web/app)
exploration, starting from a clean slate.

Checking the codebase against those 10 stages: every stage already has its
own feature-level test suite meeting `testing-standards.md`'s bar (happy
path, permission-denied, tenant-isolation — confirmed directly, e.g.
`tenant/tests.py`'s 4 tests, `visitors/tests.py`'s 36 tests covering both
visitor categories and approval workflow rules). The existing chained,
real-HTTP journey test (`tests/test_workflow_full_lifecycle.py`, added by
the already-implemented `codebase-review-and-e2e-scenario-test` change)
walks 7 of the 10 stages in one continuous flow (platform → admin login →
org structure → auth/RBAC → invitations → walk-in registration → kiosk
lookups → reports) but never calls `GET /tenants/me` (stage 02), never
exercises visitor-category/approval-workflow-rule CRUD (stage 04), and
never calls OTP request/verify (stage 08) — so nothing today proves those
three work *within* the same realistic, continuously-chained journey the
other seven do, even though each passes on its own.

Separately, the ask for "fully dynamic, no hardcode" data surfaced one
concrete, verified defect while reading `scripts/seed_dev_data.py`: its
`DEFAULT_BRANCH_CODE = "MAIN"` module constant is a second, independent copy
of the walk-in default branch code, never read from
`settings.registration_default_branch_code` the way every runtime code path
now does after `harden-default-tenant-resolution-and-readiness`. If an
operator ever changes `REGISTRATION_DEFAULT_BRANCH_CODE` without also
updating this script, re-seeding a dev environment recreates exactly the
misconfigured state that change just added a readiness check to catch.

Finally, "clear the database tables... start fresh" is a destructive action
against whatever database the seeding script is pointed at. This proposal
does not perform that action — `/opsx:propose` is planning-only — and its
design deliberately builds in a hard environment guard so the eventual
implementation can never run against a production-looking database, only
against a local/dev/test one, on explicit request.

## What Changes

- **Close the 3-stage gap in the chained lifecycle test.**
  `tests/test_workflow_full_lifecycle.py` gains three more steps, inserted
  at the point in the flow where each is contextually reachable: `GET
  /tenants/me` right after admin login (stage 02); creating a visitor
  category and an approval workflow rule referencing it, scoped to Branch A
  (stage 04); and an OTP request/verify round trip for the walk-in
  registration's primary contact email before submitting the walk-in
  registration (stage 08) — recording the returned proof token but not
  wiring it into the walk-in payload, since nothing in the API consumes
  that token yet (`docs/features/registrations.md`'s documented "No OTP
  verification" scope boundary stays unchanged; this only proves the OTP
  endpoints work inside the same realistic session as everything else).
  All 10 numbered stages are then exercised in one continuous, real-HTTP
  journey, matching the screenshot's order.
- **Fix: `scripts/seed_dev_data.py` reads the walk-in default branch code
  from `settings.registration_default_branch_code` instead of its own
  hardcoded `DEFAULT_BRANCH_CODE = "MAIN"` constant.** Re-seeding a dev
  environment after `REGISTRATION_DEFAULT_BRANCH_CODE` was changed in
  `.env` now creates a branch that actually matches the configured default,
  instead of silently reintroducing the misconfiguration
  `harden-default-tenant-resolution-and-readiness` hardened detection for.
- **Add a safety-gated reset script** (`scripts/reset_dev_tenant_data.py`).
  Discovered mid-implementation (see `design.md`'s Context, updated after
  this was found): `scripts/seed_demo_workflow.py` already exists and
  already populates realistic sample data across nearly all 10 stages —
  org structure, a visitor category with an approval workflow rule,
  invitations, OTP requests, and a walk-in registration — via real HTTP
  calls, additive and safe to re-run. The one genuinely missing piece is a
  way to clear existing data first, so that script's original plan (a new,
  combined reset-and-seed script) would have duplicated
  `seed_demo_workflow.py`'s seeding logic in a second place. Instead,
  `scripts/reset_dev_tenant_data.py` only clears every row in the one
  demo tenant's schema (`TRUNCATE`, not a schema drop — the schema's own
  migration state is left alone) plus the matching global-schema rows
  (`tenant_user_index`, `registration_device_keys`,
  `platform_audit_events`), refuses to run at all when
  `settings.environment` is `production`, and requires explicit `--yes`
  confirmation. A fresh dataset is then: `reset_dev_tenant_data.py --yes` →
  `seed_dev_data.py` → `seed_demo_workflow.py` — the same bootstrap
  sequence a brand-new environment already uses, not a second one.
- If actually running the extended lifecycle test (at apply time) surfaces
  a further genuine, reproducible bug beyond the one already found above,
  it's fixed with the smallest correct change and reported — the same
  "decide the fix when something is actually found" posture
  `codebase-review-and-e2e-scenario-test` and
  `harden-referential-integrity-and-rbac-gates` already established in this
  repo. If that happens, the fix gets its own spec delta via `/opsx:update`
  at that point, since this proposal's own scope (test coverage + dev
  tooling) has no confirmed API-behavior change to spec today.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — see `.openspec.yaml`'s `skip_specs: true`. This change adds test
coverage and dev-only tooling; it does not change any API's observable
contract. The one confirmed code fix, `seed_dev_data.py`'s hardcoded branch
code, is a dev script never reachable from any request path. If executing
the extended test surfaces a genuine API-behavior bug, that fix will get
its own spec delta added via `/opsx:update` when it's found, not invented
here ahead of evidence.)

## Impact

- **Code**: `scripts/seed_dev_data.py` (branch-code fix), new
  `scripts/reset_dev_tenant_data.py`. `scripts/seed_demo_workflow.py` is
  unchanged — it already covers the seeding side this proposal originally
  planned to duplicate.
- **Tests**: `tests/test_workflow_full_lifecycle.py` extended with 3 new
  steps; no existing assertion in that file changes.
- **Docs**: `docs/features/configuration.md`'s existing "Provisioning the
  default tenant/branch" section gains a pointer to the new reset script
  and the reset → seed_dev_data → seed_demo_workflow sequence.
- **Database**: no schema/migration changes. The new script `TRUNCATE`s the
  one demo tenant's schema when explicitly run with `--yes` — see
  `design.md`'s safety guard for exactly what is and isn't in scope for
  that, and the explicit refusal to run against a production-looking
  environment.
- **Compatibility**: no change to any endpoint's request/response contract.
