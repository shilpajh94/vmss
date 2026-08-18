## Why

Following the `pre-commit-quality-audit` change (archived), the request now is to
re-verify the full test suite is still green after that audit's fixes, and to
check that every one of the 7 feature routers' test suites actually cover every
scenario `testing-standards.md` §2 requires — the happy path for every endpoint,
at least one permission-denied case, and at least one tenant-isolation case per
feature — rather than assume the existing 186 passing tests mean full scenario
coverage. A spot-check done during this proposal already found 3 concrete,
verified gaps (below), so this isn't a purely confirmatory pass — there's real
work to close.

## What Changes

- Re-run the full `pytest` suite (baseline reconfirmed during this proposal:
  **186 passed**, unchanged since the prior audit) as the starting point, and
  again as the closing gate once new tests are added.
- Add the HTTP-level happy-path test that's missing for
  `GET /api/v1/company` (`org_structure/router.py::get_company`) — every
  existing test for this route asserts the 404 (not-yet-configured) case;
  none asserts the 200 case with a real, previously-created company returned.
- Add the HTTP-level happy-path test that's missing for
  `GET /api/v1/branches/{branch_id}` (`org_structure/router.py::get_branch`) —
  every existing test hitting this route does so only after a delete, to
  assert 404; the plain "fetch an existing branch by id" 200 case is untested.
- Add an HTTP-level happy-path test for `POST /api/v1/platform/tenants`
  (`platform/router.py::create_tenant`) — the only test that actually
  provisions a tenant (`test_create_tenant_provisions_real_schema`) calls
  `platform.service.create_tenant()` directly, deliberately bypassing the
  router (per that test's own docstring, to avoid double-provisioning cost).
  Every HTTP-level test of this route intentionally 409s/429s on a duplicate
  slug. That leaves the actual endpoint contract — `require_permission`
  dependency wiring, request validation, `Envelope[TenantSummaryOut]`
  response shape, 201 status — with no end-to-end HTTP assertion.
- Systematically re-verify (not just spot-check) that every endpoint in the
  remaining 4 feature routers (`auth`, `invitations`, `tenant`, `reports`) and
  the remaining sub-resources of `org_structure`/`visitors` has a happy-path
  test, and record the result — add a test for any further gap found.
- Document why `platform` and `tenant` have no tenant-isolation test and why
  that's correct, not a gap: both features' repositories
  (`SuperAdminRepository`, `TenantUserIndexRepository`,
  `TenantSchemaVersionRepository`, `TenantRepository`) operate on
  **global-schema** tables reachable from any session — there is no tenant
  schema for them to leak across, so `testing-standards.md` §2's
  tenant-isolation requirement doesn't apply to these two features. (No test
  added for this — it's a documented non-applicability.)

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — adding test coverage for scenarios that are already part of each
endpoint's existing, intended contract (a company/branch that exists can
already be fetched today; tenant provisioning already returns 201 with a
real body today) does not change any spec-level behavior. If closing one of
these gaps reveals an endpoint that does NOT already behave as intended, that
would be a real bug — this change's task list treats that as a stop-and-report
case (see design.md), not a silent scope expansion into a behavior change.
This change sets `skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **Affected code**: `src/vmss_api/org_structure/tests.py` (2 new tests),
  `src/vmss_api/platform/tests.py` (1 new test), and potentially
  `auth/tests.py`, `invitations/tests.py`, `tenant/tests.py`,
  `reports/tests.py`, `visitors/tests.py` if the systematic re-verification
  pass turns up further gaps.
- **No production code changes planned** — this is test-only, unless the
  systematic pass or a new test uncovers an actual bug, in which case that's
  reported before any fix is made (see design.md's Non-Goals).
- **No dependency changes.**
- **Test-suite size**: grows from 186 to at least 189 (3 known gaps), more if
  the systematic pass finds others.
