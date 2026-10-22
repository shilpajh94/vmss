## Why

The API and the web portal (VMMS_WEB) have grown by many features since the last
full pass, but nothing checks them end to end. CI runs no `pytest` stage. The
portal has no browser test suite, only a screenshot script. Nobody has load-tested
the API. The earlier ad hoc regression scripts (`scripts/qa_regression/run.py`,
`scripts/seed_qa_fixtures.py`) were never committed, and they are gone. Before the
next release we need repeatable evidence that the core visitor flows work in the
browser, through the API, and under concurrent load, with no blocker left open.

## What Changes

- Add a committed **API regression runner** in VMSS_API. It drives every router's
  main endpoints over HTTP against the local DDEV default tenant, as each QA role
  (admin, reception, security, host, approver, no-role, branch-scoped reception).
  For each call it records the status code, the envelope shape, and the latency.
- Re-create and commit an idempotent **QA fixture seeder** (QA users, roles,
  branches MAIN and QA-B, categories `QA_SINGLE`/`QA_MULTI`) that the API runner,
  the browser suite, and the load test all share.
- Add a **Playwright browser e2e suite** in VMMS_WEB for the critical portal
  journeys: admin login, org setup CRUD, the form builder, visitor categories and
  workflows, staff invitation create → approve → check-in → check-out, reception
  dashboard, visitor self-request and track, and the RBAC-hidden routes. It runs in
  the existing Playwright Docker image, so the host needs no browser libraries.
- Add a **Locust load test** in VMSS_API for the hot read and write paths (login,
  dashboards, invitation list, invitation create, check-in/out, public visit
  lookup). It runs against local DDEV with a baseline target of 50 concurrent users,
  p95 latency under 500 ms, and an error rate under 1%. The numbers are recorded as a
  baseline and are not tied to production sizing.
- Run the full existing `pytest` suite, then all three new suites. Triage every
  failure as a **blocker** or a **non-blocker**. Fix blockers in this change. Log
  non-blockers in a committed **QA findings report**
  (`docs/qa/<date>-full-stack-qa.md`) for follow-up changes.
- One command per suite, documented in `docs/features/qa-harness.md`.

No production API contract changes are intended. Blocker fixes are bug fixes that
restore behaviour the existing specs already describe. If a fix turns out to need a
spec-level change, it is called out in the report and split into its own change.

## Capabilities

### New Capabilities
- `quality-assurance`: covers the QA harness: the shared fixture seeder, the API
  regression runner, the browser e2e suite, the load test with its baseline
  thresholds, how blockers are classified, and the findings report that serves as
  the release gate.

### Modified Capabilities
<!-- None. Blocker fixes restore behaviour existing specs already require; any fix
     that would change a requirement is split into its own change (see design.md). -->

## Impact

- **VMSS_API**:
  - New `scripts/qa_regression/` (runner and fixture seeder).
  - New `loadtests/` (locustfile).
  - New dev dependency `locust`, added via `uv add --dev`.
  - New docs under `docs/qa/` and `docs/features/qa-harness.md`.
  - Targeted bug fixes in any feature package where a blocker is found.
- **VMMS_WEB**:
  - New `e2e/` Playwright suite (Python, matching the existing
    `screenshot-pages.py` tooling) and an `npm run e2e` script.
  - Targeted UI fixes where a blocker is found.
  - VMMS_WEB has no prettier, so it gets no formatter runs.
- **Local data**: the default tenant only. QA data is created there and is
  reset-safe through the seeder. No second tenant is created, except inside the
  isolated `vmss_test` pytest database.
- **CI**: out of scope. Wiring these suites into the Azure/OpenStack pipelines is a
  follow-up change. The report notes that CI currently runs no tests.
