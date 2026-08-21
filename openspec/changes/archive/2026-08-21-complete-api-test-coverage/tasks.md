## 1. Baseline

- [x] 1.1 Run `ddev exec uv run pytest` on the unmodified suite; record the exact pass/fail count, broken down per feature package.
- [x] 1.2 Diff every `require_permission("<code>")` / `require_branch_scope("<code>")` / `require_branch_permission("<code>")` string used across `src/vmss_api/*/router.py` against `ADMIN_PERMISSION_CODES` in root `conftest.py`; list any code missing from that fixture before writing tests that depend on it.

## 2. Stage 1 — Provisioning (`platform`, `tenant`) — design.md matrix rows 1-4

- [x] 2.1 Audit `platform/tests.py` against rows 1-3 (superadmin login rate-limit, tenant create duplicate-slug 409 + rate-limit, tenant list + tenant-user-token-rejected); add any missing case.
- [x] 2.2 Audit `tenant/tests.py` against row 4; add or confirm the documented non-applicability check that `TenantRepository` is global-schema-only, per design.md's "tenant feature's tenant-isolation non-applicability" decision.

## 3. Stage 2 — Auth / RBAC (`auth`) — design.md matrix rows 5-15

- [x] 3.1 Audit login (row 5) and `/auth/me` (row 6): confirm rate-limit test exists for login, and confirm `/auth/me` has no permission-denied test (only 401-unauthenticated is expected) — add either if missing.
- [x] 3.2 Audit `POST /auth/users`, branch-role assign/revoke (rows 7-9): confirm duplicate-email/employee-code conflict, invalid-branch-id, and not-found cases exist; add any missing.
- [x] 3.3 Re-verify `POST /auth/employees/sync`'s duplicate-employee-within-batch path (row 10) still returns 409, not 500 — this was fixed once in an archived change (`close-api-test-coverage-gaps`); confirm the fix and its regression test are both still present and passing, and only re-fix if it has regressed.
- [x] 3.4 Audit `GET /auth/employees` optional `X-Branch-ID` behavior (row 11), permission catalog (row 12), and roles CRUD (rows 13-15) for duplicate-name, not-found, and role-in-use-on-delete conflict cases; add any missing.

## 4. Stage 3 — Org structure (`org_structure`) — design.md matrix rows 16-19

- [x] 4.1 Audit `/company` CRUD (row 16) for the not-yet-configured-404 vs. exists-200 distinction on `GET`.
- [x] 4.2 Audit `/branches` CRUD + `/current` + `/provision` (row 17), including a test that a partial failure mid-`/provision` rolls back the whole Building→Floor→Department/Desk/Gate transaction rather than leaving partial rows.
- [x] 4.3 Audit `/buildings`, `/floors`, `/departments` (row 18) for cross-branch access denial on every CRUD op.
- [x] 4.4 Audit `/reception-desks`, `/security-gates` (row 19) for cross-branch access denial on every CRUD op.

## 5. Stage 4 — Visitor-type config (`visitors`) — design.md matrix rows 20-21

- [x] 5.1 Add permission-denied tests for `list`/`get`/`delete` on `VisitorCategory` (row 20) — currently only `create`/`update` are proven per the initial survey.
- [x] 5.2 Add permission-denied tests for `list`/`get`/`delete` on `ApprovalWorkflowRule` (row 21) — same gap.

## 6. Stage 5 — Invitation & walk-in intake (`invitations`, `registrations`) — design.md matrix rows 22-24

- [x] 6.1 Audit `POST /invitations` (row 22): confirm the validate-all-files-before-persisting-any order (no orphaned storage writes on a rejected group submission) and idempotency-key replay are both tested; add/re-verify per `close-api-test-coverage-gaps` precedent.
- [x] 6.2 Audit `GET /invitations/track` (row 23) for rate-limit and not-found cases.
- [x] 6.3 Audit `POST /registrations/walk-in` (row 24) for missing/invalid/inactive device-key, disguised-file-type + oversized-file rejection at this router's own boundary, and idempotency-key replay.

## 7. Stage 6 — Identity verification (`identity_verification`) — design.md matrix rows 25-26

- [x] 7.1 Write the Redis key-namespace isolation test described in design.md: two tenants via `TenantFactory`, assert OTP request/verify state for tenant A never leaks into or is affected by tenant B's `vmss:{tenant_id}:...` keys, reusing the existing autouse Redis-reset fixture.
- [x] 7.2 Audit rate-limit, idempotency-key replay, wrong-code, expired-code, attempt-exhaustion lockout, and no-plaintext-in-logs cases for both endpoints; add any missing.

## 8. Stage 7 — Reporting (`reports`) — design.md matrix row 27

- [x] 8.1 Extend the cross-branch rollup happy-path test to assert `security_gate_count` (and confirm every other rollup field is asserted, not just present in the fixture).

## 9. Bug fixes found during audit (fill in only if Stages 2-8 surface one)

- [x] 9.1 For each bug found that meets design.md's "fix inline" threshold: fix the specific service/router function, add the regression test that caught it, and re-run the full suite before moving to the next stage.
- [x] 9.2 For each finding that meets design.md's "stop and report" threshold: do not fix it — record it in the closing summary (task 10.4) instead.

## 10. Closing gate

- [x] 10.1 Run `ruff check` and `ruff format --check`; fix any violation in touched files.
- [x] 10.2 Run `mypy` on any touched module under `core/`, `auth/`, or handling money/PII, per `project-rules.md`'s strict-typing scope.
- [x] 10.3 Run the full `ddev exec uv run pytest` suite; confirm the pass count only grew relative to the task 1.1 baseline, with zero failures.
- [x] 10.4 Write a closing summary: baseline count vs. final count, list of gaps closed per stage, list of bugs fixed (with the regression test for each), and list of stop-and-report findings left open for a follow-up change.
- [x] 10.5 Update the relevant `docs/features/<feature>.md` file(s) if any audited behavior differs from what's currently documented there.
