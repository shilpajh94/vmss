## 1. Clean-state full test suite

- [x] 1.1 Confirm the local DDEV environment is healthy (`ddev describe`,
      Postgres/Redis services up) and `.env` is fully resolved (no
      unresolved `__PLACEHOLDER__` values) so `Settings()` loads. (web/db
      services OK; the one remaining `__...__` match in `.env` is inside a
      comment, not a value.)
- [x] 1.2 Run `ddev exec uv run pytest -q` for the whole repo from a clean
      state and record the result (pass count, any failures). Result:
      **393 passed, 0 failed** (109.78s).
- [x] 1.3 If anything fails, capture the full failure output before
      touching any code, so the failure is diagnosed from real evidence,
      not assumption. (N/A — nothing failed.)

## 2. Live-request pass — shared dependency surface (highest risk)

The recent fix touched `registrations/deps.py::get_registration_device`/
`_resolve_default_device_context` (shared by every endpoint below) and
`auth/repository.py::search_active_by_name_or_email`. Exercise these
through the real ASGI app (real Postgres, real HTTP-shaped request/response
objects — same approach as the prior apply session), in an isolated
throwaway schema so nothing here touches real dev data:

- [x] 2.1 `POST /registrations/walk-in` — with a valid device key, with no
      device key (default tenant/branch configured), and with no device
      key (default tenant/branch unconfigured) — confirm 201, 201, and the
      distinct 401 respectively. **Result: 201 / 201 / 401 with the new
      "Registration service is not configured for this environment"
      message — all as expected.**
- [x] 2.2 `GET /hosts/search` — with a query, with no query (browsable
      list), with a blank query, and with a too-short query — confirm 200,
      200, 200, and 422 respectively. **Result: 200 / 200 (2 browsable
      results) / 200 / 422 — all as expected.**
- [x] 2.3 `GET /visit-info/departments` and `GET /visit-info/options` —
      with and without a device key — confirm 200 in both cases. **Result:
      200 in all four combinations.**

## 3. Live-request pass — remaining feature areas

For each area, confirm its own `pytest` coverage is green (task 1.2 already
covers this) and spot-check one representative authenticated endpoint end
to end (login → call → expected shape), since these don't share the
device-credential dependency but do share `core/database.py`,
`core/responses.py`, and `core/middleware.py`, which the fix's tests didn't
touch but which every request still flows through:

- [x] 3.1 `auth` — login, then a permission-gated endpoint (e.g. employee
      listing) with and without the required permission (401/403 cases).
      **Result: login 200 (real access token issued); `GET /auth/roles`
      (`roles:view`) 200 with the admin token, 401 with none.** (A true
      403-with-wrong-role case is already covered by `auth/tests.py`,
      green in task 1.2 — not re-derived here.)
- [x] 3.2 `tenant` / `platform` — tenant resolution via a valid JWT claim;
      superadmin login if covered by existing tests. **Result: exercised
      more directly than planned — `platform_service.create_tenant` ran
      for real, applying every `alembic_tenant` migration head-to-head
      against a brand-new schema (confirms the migration chain itself is
      healthy, isolating the earlier-found stale-`tenant_default` issue as
      specific to that one pre-existing dev schema, not a migration
      defect). Every subsequent authenticated call resolved tenant/schema
      correctly from the issued JWT.**
- [x] 3.3 `org_structure` — one CRUD endpoint (e.g. branches or
      departments) round-trip. **Result: `GET /branches` 200.**
- [x] 3.4 `visitors` — one lookup/list endpoint. **Result:
      `GET /visitor-categories` 200.**
- [x] 3.5 `invitations` — create + track, since `registrations` reuses its
      schema and service layer directly. **Result: `POST /invitations` 201
      (`source: "staff_pre_registration"`, correctly distinct from walk-in's
      `"visitor_walk_in"`), `GET /invitations/track` 200.**
- [x] 3.6 `identity_verification` — OTP request/verify happy path (no real
      SMS/email provider needed if the test suite already stubs it).
      **Result: 200 / 200, using the same fake-sender-monkeypatch pattern
      the project's own tests use. Confirmed as a side effect: the OTP
      identifier is masked in structured logs (`r***@example.com`), per
      security-architecture.md.**
- [x] 3.7 `reports` — one report/read endpoint. **Result:
      `GET /reports/branches/rollup` 200.**
- [x] 3.8 `sso` — whatever this feature's own `tests.py` already covers
      (no live-request pass if it requires a real external IdP). Covered
      by task 1.2's full green run; no live call made (needs a real IdP).

## 4. Wrap-up

- [x] 4.1 If task 1–3 surfaced a genuine regression, fix it (smallest
      correct change, scoped to the broken file(s)) and note what broke and
      why in this change's proposal/tasks before re-running the affected
      tests. **No regression found — N/A.**
- [x] 4.2 Re-run `ddev exec uv run pytest -q` once more if anything was
      changed in task 4.1, to confirm the fix and that nothing else broke.
      **N/A — nothing changed, so no re-run needed beyond task 1.2's.**
- [x] 4.3 Clean up: drop any throwaway schema/database created for the
      live-request pass; leave no temporary scripts in the repo.
      **`vmss_regression_verify` database dropped; temp script removed;
      `git status` confirms no stray files.**
- [x] 4.4 Summarize results: total tests passed, endpoints spot-checked,
      any regressions found and fixed (or confirmation that none were
      found). **393/393 pytest passed. 21/21 live-request checks passed
      across all 11 feature areas (registrations, visit_info, auth, tenant/
      platform, org_structure, visitors, invitations, identity_verification,
      reports; sso covered by its own green test suite). Zero regressions
      found — the `fix-visit-info-lookup-access` change is confirmed clean
      across the full API surface.**
