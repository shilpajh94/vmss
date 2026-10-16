## 1. Environment & Baseline

- [x] 1.1 `ddev start`; run `scripts/upgrade_all_tenants.py`; confirm only `tenant_default` exists locally (run `prune_non_default_tenants.py` if not); record both repos' commit SHAs and DDEV service versions for the report
- [x] 1.2 Create a clean-HEAD baseline worktree (`git worktree add --detach .baseline-wt HEAD`, copy `.env` in) and run the full pytest suite there once, sequentially; save the failure list to `var/qa/pytest-baseline.txt`
- [x] 1.3 Run the full pytest suite on the working tree (sequentially, never concurrently); save to `var/qa/pytest-current.txt`; diff against the baseline and list regressions vs pre-existing failures

## 2. Shared QA Fixtures

- [x] 2.1 Create `scripts/qa_regression/__init__.py` and `seed_qa_fixtures.py`. Upsert QA users (admin, reception, security, host, approver, no-role, QA-B-only reception, all `@example.com`), branches MAIN/QA-B, and categories `QA_SINGLE`/`QA_MULTI` by natural key. Refuse any schema other than `tenant_default`
- [x] 2.2 Create `scripts/qa_regression/mint_tokens.py` writing per-role access tokens (TTL ≤ 6 h) to the gitignored `var/qa/tokens.json`
- [x] 2.3 Create `scripts/qa_regression/reset_qa_data.py --yes` that deletes only `QA`-prefixed invitations and visitors and their child rows in `tenant_default`
- [x] 2.4 Verify: the seeder run twice leaves row counts unchanged; pointing it at a non-default schema exits non-zero with no writes

## 3. API Regression Runner

- [x] 3.1 Implement `scripts/qa_regression/run.py`: a declarative call table `(router_tag, method, path, role, payload_builder, expected_status)`, an httpx client against the live API, envelope-shape check, latency capture, JSON results in `var/qa/api-results.json`, and a console summary
- [x] 3.2 Add the router-coverage check against live `/openapi.json` tags; an uncovered router fails the run
- [x] 3.3 Populate happy-path entries for every registered feature router (auth, tenant, platform, org_structure, visitors, invitations, approvals, registrations, form_builder, kiosks, devices, identity_verification, notifications, dashboard, reports, audit_trail, visit_info, visitor_return_visit, sso), including the full invitation lifecycle create → approve → check-in → check-out on `QA_MULTI`
- [x] 3.4 Add negative entries: no-role 403 on protected endpoints, QA-B reception rejected on a MAIN resource via `X-Branch-ID`, 401 with no or invalid token, a rate-limiter 429 on a public endpoint, and an idempotent retry of check-in with the same `Idempotency-Key` returning the cached response
- [x] 3.5 Run it against the seeded stack; record every failure as a finding (see section 7)

## 4. Browser E2E Suite (VMMS_WEB)

- [x] 4.1 Build the `vmss-e2e:local` image from the Playwright Python image with `playwright==1.55.0`, `pytest`, `pytest-playwright`; add `npm run e2e` wrapping `docker run --rm --network host --user $(id -u):$(id -g) -e HOME=/tmp`
- [x] 4.2 Create `VMMS_WEB/e2e/conftest.py`: a `role_page(role)` fixture injecting tokens from `tokens.json` into `sessionStorage`, an admin password-login fixture, and an autouse pageerror/5xx collector that fails the test and saves a screenshot and trace to `e2e-results/`
- [x] 4.3 Deliberately add `e2e-results/` to `VMMS_WEB/.gitignore` (an explicit, reviewed change to `.gitignore`)
- [x] 4.4 Journeys: admin login and logout; org structure create and edit (branch, building, floor, department); form builder step edit and save
- [x] 4.5 Journeys: visitor category and approval workflow create and edit; roles page loads; kiosks list
- [x] 4.6 Journey: staff invitation create (`QA_MULTI`) → reception approve → host-approver approve → check-in → check-out, asserting the status in the UI at each step
- [x] 4.7 Journeys: reception dashboard; staff dashboard; visitor self-request (`/visitor/request`) and track (`/visitor/track`)
- [x] 4.8 Journey: RBAC guard — the no-role and reception users opening `/admin/*` routes do not see admin content
- [x] 4.9 Run the suite (Vite on :5173 + DDEV); rerun intermittent failures once before recording; record findings

## 5. Load Test

- [x] 5.1 `uv add --dev locust`; create `loadtests/locustfile.py` with `StaffUser` (3), `ReceptionUser` (2, idempotent writes on `QA_SINGLE` with `QA LOAD` names), and `PublicUser` (1, visit-info lookup), all using pre-minted tokens
- [x] 5.2 Add an `events.quitting` gate: aggregate p95 < 500 ms, error rate < 1%, zero 5xx; on breach set a non-zero exit code and print the offending endpoints
- [x] 5.3 Find how slowapi limits are configured. If no setting exists to raise or disable them, add one through `settings` (default = current behaviour) with a `.env.example` placeholder entry. Enable the override in local `.env` for the load run only
- [x] 5.4 Run headless: `--users 50 --spawn-rate 10 --run-time 5m --csv var/qa/load` with Celery running. On a breach, rerun once, then profile the offending endpoints (query count, missing eager loads)
- [x] 5.5 Revert the `.env` override; re-run the API runner's 429 case to confirm the limiter is active; run `reset_qa_data.py --yes`

## 6. Blocker Fixes

- [x] 6.1 Classify every finding from sections 1, 3, 4 and 5 against the spec's blocker definition. Anything needing a spec or contract change gets a named follow-up change instead of a fix here
- [x] 6.2 For each in-scope blocker, make one `fix:` commit with a regression test (pytest for API, including permission-denied and tenant-isolation cases where RBAC or scoping is involved; an e2e assertion for UI)
- [x] 6.3 Re-run the suite that found each blocker and confirm it passes; re-run the full pytest suite (sequentially) and diff against the baseline to confirm no new regressions
- [x] 6.4 Lint and type gates: `ruff check`, `ruff format --check`, `mypy` on touched `core/`, `auth/` or PII modules; `npm run lint` and `npm run build` in VMMS_WEB (no prettier)

## 7. Report & Docs

- [x] 7.1 Write `docs/qa/2026-10-full-stack-qa.md` with: environment, per-suite summary, load baseline table (p50, p95 and p99 per endpoint), findings table (id, suite, blocker/non-blocker, repro, fixing commit or follow-up), and the verdict
- [x] 7.2 Write `docs/features/qa-harness.md` covering the seed, mint, run, e2e, load and reset commands, the env vars, the rate-limit override procedure, and the known pre-existing pytest failures
- [x] 7.3 Confirm the verdict is "no open blockers", or list the open blockers with their follow-up changes. Update the memory notes that reference the old uncommitted QA scripts
