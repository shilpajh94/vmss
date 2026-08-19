## 1. Bug Fix: Invitation ID-Proof Upload Ordering

- [x] 1.1 In `invitations/service.py::create_invitation`, split the per-visitor loop into two
      passes: validate every visitor's (and the primary contact's) ID proof file content/type
      and size first (no storage I/O), then persist all files to storage only once every one
      has passed validation.
- [x] 1.2 `invitations/tests.py`: add the regression test for the new spec scenario — a group
      submission where an earlier visitor's file is valid and a later visitor's file is
      disguised/invalid; assert the submission is rejected AND the earlier visitor's file was
      never written to storage (inspect the storage backend used in tests, e.g. via the local
      storage root or a spy on `core.storage.save`).
- [x] 1.3 Confirm the existing 29 `invitations/tests.py` tests still pass unmodified.

## 2. auth (API-01/02) — Employee Sync Duplicate-Batch Test

- [x] 2.1 `auth/tests.py`: add a test for `POST /employees/sync` where the batch contains two
      entries with the same employee code or email, asserting the 409 raised by the
      `IntegrityError` handling at `auth/service.py:376-380` (currently only the
      unknown-department-404 branch is tested for this endpoint).
- [x] 2.2 **Bug found while adding 2.1**: the new test initially failed with an unhandled 500.
      `create_user` (called per new item inside `sync_employee_directory`'s loop) flushes
      internally, so a duplicate `employee_code`/email within the batch raised `IntegrityError`
      during the loop — before execution ever reached the `try/except` that only wrapped the
      final `tenant_db.commit()`. Fixed by wrapping the entire loop, the batch flush, and the
      commit in one `try/except IntegrityError` block, so the 409 translation fires regardless
      of which flush point surfaces the constraint violation.

## 3. visitors (API-05/06) — Permission-Denied Completeness

- [x] 3.1 `visitors/tests.py`: add permission-denied tests for `GET` (list), `GET`
      (single), and `DELETE` on `VisitorCategory` for a caller without the relevant
      permission (currently only `create`/`update` are proven to reject).
- [x] 3.2 `visitors/tests.py`: add the same three permission-denied tests for
      `ApprovalWorkflowRule`.

## 4. platform (API-07) — Deterministic Duplicate-Slug Test

- [x] 4.1 `platform/tests.py`: add `test_create_tenant_duplicate_slug_returns_409` — two
      `POST /platform/tenants` calls with the same slug (limiter left at its test-environment
      default of disabled), asserting the second call is unambiguously 409. Leave
      `test_create_tenant_rate_limit_trips` unchanged.

## 5. core/API-08 — Rate-Limit Response Envelope

- [x] 5.1 `tests/test_api_documentation.py`: add a test that trips the rate limit on
      `GET /invitations/track` (flipping `limiter.enabled` on, per the existing pattern in
      `invitations/tests.py::test_track_rate_limit_trips`) and asserts the 429 response body
      has `success: false` and a non-empty `message`, per
      `openspec/specs/rate-limiting/spec.md`'s third requirement.

## 6. registrations (API-13/14) — HTTP-Boundary File Validation Smoke Test

- [x] 6.1 `registrations/tests.py`: add a disguised-file-type rejection test and an
      oversized-file rejection test against `POST /registrations/walk-in`, mirroring the
      equivalent tests already in `invitations/tests.py` but asserting at this router's own
      boundary.

## 7. reports — Rollup Field Coverage

- [x] 7.1 `reports/tests.py`: extend the `branch_with_org_chart` fixture (or add a sibling
      fixture) to include a security gate, and assert `security_gate_count` in the existing
      cross-branch rollup happy-path test.

## 8. Verification

- [x] 8.1 `ddev exec uv run pytest` full suite green, including every new test in sections
      1-7. (241 passed.)
- [x] 8.2 `ruff check` and `ruff format --check` clean. (`ruff format` auto-wrapped 4 lines
      in `auth/tests.py`/`visitors/tests.py` that exceeded the 100-char limit; no logic
      changed, confirmed by re-running both files' tests after formatting.)
- [x] 8.3 `mypy` clean on `src/vmss_api` (82 source files, no issues).
- [x] 8.4 Confirm no existing test's assertions changed — this change is additive except for
      the two reorderings: `invitations/service.py::create_invitation` (validate-before-persist,
      task 1.1) and `auth/service.py::sync_employee_directory` (widen the `IntegrityError`
      try/except to cover the whole loop, task 2.2 — a bug fix found while adding task 2.1's
      test, beyond the original task list).
