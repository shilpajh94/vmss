# Full-stack QA: October 2026

**Verdict: no open blockers.** Four blockers were found, fixed, and
re-verified by the suite that found each one. Fourteen non-blockers are
listed below with follow-ups. The 50-user load gate fails on latency alone,
with no errors and no 5xx. As decided during this pass, that is recorded as
a capacity baseline (L1), not as a blocker.

Change: `openspec/changes/full-stack-qa-and-load-testing/`. How to run every
suite: `docs/features/qa-harness.md`.

## Environment

| | |
|---|---|
| Date | 2026-10-16 |
| VMSS_API | `feature/suggestions-fix`, from `b7886bd` to `90cba55` (fixes below) |
| VMMS_WEB | `feature/suggestions-fix`, from `91eae49` to `6882b11` (e2e suite) |
| Stack | DDEV 1.25.3 on WSL2: 8 vCPU, 7.6 GB RAM (swap almost full under load), PostgreSQL 17.6, Redis 7.4, Python 3.13, Celery worker and beat running |
| Data | Local default tenant only (`tenant_default`), with QA fixtures from `seed_qa_fixtures.py` |

## Results by suite

| Suite | Result |
|---|---|
| `pytest` (full) | Baseline at `b7886bd`: 250 failed, 1301 passed. After the fixes: 236 failed, 1317 passed. No new failures against the baseline, and 14 baseline failures now pass. The remainder is the pre-existing set T1–T3. |
| API regression runner | 218 calls across all 23 router tags: 0 failures, 2 known (F2) |
| Browser e2e | 21 passed, 2 xfailed (F7) |
| Load test (50 users) | Gate fails on p95 (1.3 s with 1 process, 820 ms with 2). 0 errors, 0 5xx. See L1. |

## Blockers (all fixed)

| id | Found by | What was wrong | Fix |
|---|---|---|---|
| F1 | API runner, pytest | `GET /tenants/me` returned 500. Since `ae7b44a`, `get_tenant` returns a `TenantContext` without `name`/`slug`, so building `TenantOut` failed. | `04b4ef6` |
| F4 | API runner, browser | `require_permission` accepted company-wide grants only, so branch-scoped Reception got 403 reading workflow rules, roles and permissions. The invitation board then guessed approval levels: "Level 2/2" on Reception's own first step, no "Approve & Delegate", and every employee offered as a delegate. The auth spec requires branch-scoped grants to work. | `4011407` |
| F9 | pytest | Provisioning a tenant whose slug has a hyphen (the slug pattern allows `-`) returned 500 and left a half-migrated schema: six tenant migrations interpolated the schema name unquoted. | `1449277` |
| F10 | pytest, then live check | The unauthenticated QR check-in/out response carried a signed URL to the visitor's ID-proof document (e.g. Aadhaar), plus co-visitor and file-upload documents. The invitations spec forbids this. **Mobile/gate clients that started reading `primaryContactIdProofUrl` there must use the staff detail view.** | `4fd521b` |

Each fix commit includes a regression test. For each blocker, the suite that
found it was re-run and passes:

- **F1:** `tenant/tests.py::test_get_my_tenant` and the runner's `tenants` cases.
- **F4:** `visitors/tests.py::test_branch_scoped_grant_can_read_workflow_catalog`,
  the runner's branch-scoped reception cases, and the e2e lifecycle's
  "Level 1/2" assertion.
- **F9:** `platform/tests.py::test_create_tenant_provisions_real_schema`.
- **F10:** `invitations/tests/::test_qr_check_in_response_includes_id_proof_type_but_never_a_document_url`
  and a live QR check-in.

Also fixed, not a blocker: `266793e` makes invitation QR rendering 3.5×
cheaper (L1).

## Non-blockers

| id | Found by | Finding | Follow-up |
|---|---|---|---|
| F2 | API runner | Request-validation 422s use FastAPI's default `{"detail": [...]}` body, not the envelope. `VMMS_WEB/src/data/api/api-error.ts` parses that shape, so enveloping it is a contract change. | New change: envelope validation errors under the versioning rule, coordinated with web and mobile. |
| F3 | API runner | A host who creates an invitation gets 404 on it until a step is delegated to them. This matches the spec: the relevance rule's clauses (a)–(e) have no creator clause. | Product decision. Extend `delegator-retains-invitation-visibility` (currently empty) or a new change. |
| F5 | API runner | A building can be soft-deleted while it still has active floors, departments and desks. Only branch deletion is guarded. | Optional: extend "Branch Deletion Is Blocked While Actively Referenced" to buildings and floors. |
| F6 | API runner | The public `GET /branches` (intentionally unauthenticated) also returns `contactEmail`, `contactPhone`, `contactPersonUserId` and `notes`. | Privacy review: a slimmer public branch schema. |
| F7 | Browser | `/admin/*` has no client-side role guard: no-role and Reception users get the admin shell with error states. The API still refuses the data and every action. | Web change: role-gate `AdminLayout`. The e2e journey is a strict xfail until then. |
| F8 | Browser | The web `app-shell` spec says a 401 *or* 403 ends the session. `api-client.ts` deliberately handles only 401 (403 means "not permitted"). | Update the web spec to match the code. |
| F11 | Browser | The staff and visitor forms submit the purpose option's value (`business-meeting`) as `purposeOfVisit`, so the board and the review step show the slug. | Web: send or display the option label. |
| F12 | Browser | The branch form validates Physical Address as required, but its label has no `*`. | Web: mark the field required. |
| F13 | Browser | The admin create forms (seen on Add Building) discard input typed before their reference data has loaded. | Web: don't reset form state when options arrive. |
| L1 | Load test | Latency-only gate breach at 50 users. See below. | New change: per-request auth loading cost, plus production worker/replica sizing. |
| T1 | pytest | About 120 `MissingGreenlet` failures. `get_tenant`'s registry-session rollback expires objects in the single session the `client` fixture shares with the app. Production uses separate sessions, and the runner covers the same endpoints live. | Test-infra change: give the test override separate sessions. |
| T2 | pytest | About 85 failures: test payloads lack `visitDetails.branchId`, required since `8ec5b06`. | Test-data refresh. |
| T3 | pytest | A few stale tests: a dict-shaped `consents`, an `IdProofType` import. | Test-data refresh. |
| T4 | Harness | `pytest` uses the dev Redis, and its client is `127.0.0.1`, so it uses up the live rate-limit counters. Running the runner at the same time produces 429s. | `isolate-test-storage-and-cache` (proposed, 0/7 tasks). |

## L1: load baseline

The user mix:

- `StaffUser` ×3: lists and dashboards.
- `ReceptionUser` ×2: create, approve, gate check-in, check-out.
- `PublicUser` ×1: tracking lookup and visit-info options.

Rate limiting was off for the runs (`RATE_LIMIT_ENABLED=false`) and debug
SQL echo was off. The target was a prod-like `uvicorn` with no `--reload`,
on `:8001`. Each figure is one run.

| Users | Processes | Requests/s | p50 | p95 | p99 | Errors | Gate |
|---|---|---|---|---|---|---|---|
| 25 | 1 | 16.6 | 59 ms | 260 ms | 450 ms | 0 | pass |
| 35 | 1 | 22.7 | 91 ms | 400 ms | 640 ms | 0 | pass |
| 50 | 1 | 25.7 | 350 ms | 1300 ms | 2000 ms | 0 | **fail** |
| 50 | 2 | 28.9 | 180 ms | 820 ms | 2200 ms | 0 | **fail** |

Per endpoint at 50 users, 1 process (p50 / p95):

| Endpoint | p50 | p95 |
|---|---|---|
| `POST /invitations` | 630 ms | 2000 ms |
| `POST /approval-steps/{id}/approve` | 530 ms | 1600 ms |
| `GET /invitations?relevantToMe` | 500 ms | 1100 ms |
| `GET /dashboard/my-overview` | 420 ms | 1200 ms |
| `GET /invitations` (branch list) | 290 ms | 880 ms |
| `GET /dashboard/overview` | 280 ms | 950 ms |
| `GET /visit-info/options` | 280 ms | 930 ms |
| `GET /invitations/track` | 270 ms | 930 ms |
| `PATCH /v2/invitations/{trackingId}/check-in` | 250 ms | 810 ms |
| `PATCH /invitations/{id}/check-out` | 250 ms | 780 ms |

Why: one Python process becomes CPU-bound at about 22–26 requests/s
(about 40 ms of CPU per request). Every endpoint then queues behind the
others, which is why even `visit-info/options` (16 ms unloaded) reaches
about 280 ms. A py-spy profile under load showed:

- **About 45% of server CPU** in SQLAlchemy ORM loading, chiefly the
  user → role → permission selectin chain every authenticated request loads.
- **About 20%** rendering the invitation QR on approval. Fixed in `266793e`:
  18 → 5 ms per render.

Postgres stayed mostly idle (≤2 active queries). Production also runs a
single `uvicorn` process (`Dockerfile` `CMD`, no `--workers`). The
follow-up should:

- profile and cache the per-request permission load,
- size workers and replicas for the expected desk and kiosk count,
- re-run this test on staging-like hardware.

## Status after `audit-and-harden-api-and-web` (2026-10-22)

| id | Status |
|---|---|
| F1, F4, F9, F10 | Fixed earlier (regression tests above). |
| F2 | Open. A breaking envelope change, tracked as gap G22. |
| F3 | Open. A product decision, tracked as G25. |
| F5 | Open. Changes a status code, tracked as G23. |
| F6 | Open. Tracked as G24; it will fold into public-endpoint-hardening strict mode. |
| F7 | Web half of this change: permission-gated `AdminLayout` (web D-W3). |
| F8 | Web half: the web spec now says only a 401 ends the session. |
| F11, F12, F13 | Web half (purpose label, required markers, dirty tracking). |
| L1 | Partly addressed: the S3 presigner is cached and the current user loads through one explicit loader. Caching the per-request permission load (the ~45% CPU hot spot) is tracked as G41. |
| T1 | **Fixed.** The test client's `get_db` gets its own session, so `get_tenant`'s rollback no longer expires shared objects. |
| T2 | **Fixed.** `factories.with_default_location` fills `visitDetails.branchId`/`buildingId`. |
| T3 | **Fixed.** The stale `IdProofType` import and dict-shaped `consents` are gone, and the OTP regex is updated. |
| T4 | **Fixed** (`isolate-test-storage-and-cache`): a temporary storage root and Redis db 15. |

Full suite: **240 failed → 0 failed** (1772 passed on 2026-10-22; an
intermittent teardown-race 401 still shows up occasionally and passes in
isolation). The G38 xfail was resolved later the same day: a zero-visitor
group registration is now rejected.

### L1 re-run (2026-10-22)

The same 50-user, 1-process set-up, but the absolute numbers are **not
comparable** to the L1 table above. The workstation was busier: the
dev `--reload` server, the auto-reloading Celery worker and Vite, with a
load average of about 6.6. `tenant_default` also held 832 invitations
instead of an empty table. So the change was judged by an A/B on the
same machine, minutes apart: HEAD (`f7ba135`) served from a worktree
against the same database, then the working tree.

| Build | Requests (2 min) | p50 | p95 | p99 | Errors | 5xx |
|---|---|---|---|---|---|---|
| HEAD, run 1 | 1877 | 1300 ms | 3200 ms | 4600 ms | 0 | 0 |
| This change | 1797 | 1400 ms | 3600 ms | 4800 ms | 1¹ | 0 |
| HEAD, run 2 | 1759 | 1400 ms | 3900 ms | 5200 ms | 0 | 0 |

¹ A connection reset when locust stopped at the run-time limit, not a
server error.

This change sits between the two HEAD runs, so there is **no measurable
throughput regression**. A py-spy profile under load still shows ORM
loading as the main cost. The explicit permission loader
(`get_with_permissions`) accounts for about 6% of request CPU. The
throughput ceiling is still L1's single process, and G41 plus worker
sizing are the follow-ups.

## Releasing

The merge preconditions, deploy order and rollback for this work are in
`docs/release/2026-10-audit-and-harden.md`. The changes the Flutter app has
to make are in `docs/clients/mobile-app-migration.md`.

## Reproducing

See `docs/features/qa-harness.md`. Raw artifacts from this pass (runner
JSON, Locust CSVs, py-spy samples) were in the gitignored `var/qa/` and are
not committed.
