## 1. Baseline

- [x] 1.1 Run the full `ddev exec uv run pytest` suite; confirm the current
      total (expected 186 passed, matching the state at proposal time).
      **Confirmed: 186 passed.**

## 2. Close Confirmed Gap 1 — `GET /api/v1/company` Happy Path

- [x] 2.1 Add `test_get_company_success` to `org_structure/tests.py`: create a
      company via `POST /api/v1/company`, then `GET /api/v1/company`, assert
      200 and that the response body matches what was created.
- [x] 2.2 Run `org_structure/tests.py` — confirm the new test passes and
      nothing else regresses. **79 passed (78 + 1 new).**

## 3. Close Confirmed Gap 2 — `GET /api/v1/branches/{branch_id}` Happy Path

- [x] 3.1 Add `test_get_branch_success` to `org_structure/tests.py` using the
      existing `branch` fixture: `GET /api/v1/branches/{branch.id}`, assert
      200 and that the response body matches the fixture's branch.
- [x] 3.2 Run `org_structure/tests.py` — confirm the new test passes and
      nothing else regresses. **80 passed (79 + 1 new).**

## 4. Close Confirmed Gap 3 — `POST /api/v1/platform/tenants` Happy Path

- [x] 4.1 Add an HTTP-level happy-path test to `platform/tests.py` (e.g.
      `test_create_tenant_success_via_endpoint`) that logs in as the
      `superadmin` fixture, calls `POST /api/v1/platform/tenants` with a
      fresh unique slug, and asserts a 201 with an
      `Envelope[TenantSummaryOut]`-shaped body.
- [x] 4.2 Drop the schema the new test provisions in a `finally`/teardown
      block, following `test_create_tenant_provisions_real_schema`'s existing
      cleanup pattern, so the test doesn't leave schema bloat in `vmss_test`.
- [x] 4.3 Run `platform/tests.py` — confirm the new test passes and nothing
      else regresses. **9 passed (8 + 1 new).**

## 5. Systematic Re-Verification — Remaining Routers

- [x] 5.1 `auth` (6 endpoints): confirm each of login, get-my-profile,
      create-user, assign-branch-role, sync-employee-directory,
      list-employees has a genuine happy-path test. Add any missing one.
      **All 6 confirmed genuine (each calls its route and asserts a success
      status/body) — no gap.**
- [x] 5.2 `invitations` (2 endpoints): confirm create-invitation (both
      individual and group variants) and track-by-tracking-id each have a
      genuine happy-path test. Add any missing one. **Both confirmed
      genuine — no gap.**
- [x] 5.3 `tenant` (1 endpoint): confirm get-my-tenant has a genuine
      happy-path test. Add if missing. **Confirmed genuine — no gap.**
- [x] 5.4 `reports` (1 endpoint): confirm the cross-branch rollup endpoint
      has a genuine happy-path test. Add if missing. **Confirmed genuine —
      no gap.**

## 6. Systematic Re-Verification — Remaining `org_structure`/`visitors` Sub-Resources

- [x] 6.1 `org_structure` building/floor/department/reception-desk/security-gate
      (5 endpoints each): re-confirm each sub-resource's create/list/get/update/delete
      routes each have a genuine happy-path test (proposal-time spot-check
      found these already covered — re-verify against the current file
      rather than trusting that read). Add any gap found. **All 20 (5
      sub-resources × 4 actions, plus the 5 get-by-id tests checked
      separately) confirmed genuine — no gap.**
- [x] 6.2 `visitors` category/workflow-rule (5 endpoints each): same
      re-confirmation. Add any gap found. **All 10 confirmed genuine — no
      gap.**

## 7. Final Gate

- [x] 7.1 Full `ddev exec uv run pytest` — confirm all pass, report the new
      total (≥189). **189 passed (186 + 3 new).**
- [x] 7.2 `ruff check .` and `ruff format --check .` clean on the modified
      test files. **Both clean.**
- [x] 7.3 If any task above surfaced a genuine production bug (per
      design.md Decision 3), stop here and report it instead of silently
      patching it — do not close this task list until that's been
      surfaced to the user. **No production bug surfaced — the systematic
      pass (task groups 5-6) found every other endpoint already had genuine
      happy-path coverage. Nothing to report; task list closes clean.**
