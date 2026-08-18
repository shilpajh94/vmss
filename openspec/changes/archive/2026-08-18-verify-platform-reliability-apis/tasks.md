## 1. Re-Audit API-07 and API-08 (no code change)

- [x] 1.1 Confirmed `POST /branches/provision` bootstraps a full org-chart
      tree in one transaction, gated by its own `branches:provision`
      permission, already hardened by `harden-org-structure-crud`'s
      partial-unique-index fix.
- [x] 1.2 Confirmed `GET /reports/branches/rollup` aggregates correctly via
      grouped-by-branch queries (no per-branch loop), reports zero rows for
      empty branches, and is tenant-isolation-tested at the repository
      level — 3 passing tests already cover this thoroughly.
- [x] 1.3 Confirmed OpenAPI schema completeness/security/camelCase/
      docs-gating via `tests/test_api_documentation.py` (all passing).
- [x] 1.4 Confirmed versioning is compliant by inspection — exactly one
      version exists, nothing to test beyond current coverage.
- [x] 1.5 Confirmed `slowapi` rate limiting is correctly wired
      (`core/rate_limit.py`, `main.py`) and applied via `@limiter.limit(...)`
      to `POST /auth/login` (5/min), `POST /platform/auth/login` (5/min),
      and `POST /platform/tenants` (3/min) — but confirmed via
      `grep -rn "429\|RateLimitExceeded"` across every `tests.py` that only
      `invitations/tests.py` exercises the 429 path; `auth`/`platform`
      have none.

## 2. Close the Rate-Limit Test-Coverage Gap (design.md Decision 1)

- [x] 2.1 Added `test_login_rate_limit_trips` to `auth/tests.py` — mirrors
      `invitations/tests.py::test_track_rate_limit_trips`.
- [x] 2.2 Added `test_platform_login_rate_limit_trips` to `platform/tests.py`.
- [x] 2.3 Added `test_create_tenant_rate_limit_trips` to `platform/tests.py`
      — authenticated as superadmin, reuses the existing `tenant` fixture's
      slug on every request so each call 409s on the slug-conflict check
      rather than actually provisioning a new schema per request; only the
      429 path is exercised.

## 3. Capability Specs (design.md Decision 2)

- [x] 3.1 `reports` baseline delta spec already written during `/opsx:propose`
      at `openspec/changes/verify-platform-reliability-apis/specs/reports/spec.md`.
      Syncs into `openspec/specs/reports/spec.md` at archive time, same
      workflow as the `auth`/`org-structure`/`visitors` baselines established
      in this session's prior three archived changes.
- [x] 3.2 `rate-limiting` baseline delta spec already written at
      `openspec/changes/verify-platform-reliability-apis/specs/rate-limiting/spec.md` —
      syncs at archive time.
- [x] 3.3 `org-structure`'s "Bulk Branch Provisioning" MODIFIED requirement
      already written at
      `openspec/changes/verify-platform-reliability-apis/specs/org-structure/spec.md` —
      syncs into the existing `openspec/specs/org-structure/spec.md` at
      archive time.

## 4. Final Verification

- [x] 4.1 `ddev exec uv run ruff check` and `ddev exec uv run ruff format --check`
      clean on `src/vmss_api/auth/` and `src/vmss_api/platform/`.
- [x] 4.2 `ddev exec uv run mypy src/vmss_api/auth src/vmss_api/platform` —
      clean (16 source files).
- [x] 4.3 `ddev exec uv run pytest src/vmss_api/auth/tests.py src/vmss_api/platform/tests.py`
      — 28 passed (all existing cases plus the 3 new cases).
- [x] 4.4 Full `ddev exec uv run pytest` — 174 passed (171 + 3 new), zero
      regressions.
