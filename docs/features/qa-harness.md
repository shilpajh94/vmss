# QA harness

Three suites that check the API and the web portal end to end against the
running local stack, on top of the `pytest` suite. Built in
`openspec/changes/full-stack-qa-and-load-testing/`; the latest findings
are in `docs/qa/`.

| Suite | Lives in | Checks | Runtime |
|---|---|---|---|
| API regression runner | `scripts/qa_regression/run.py` | Every router's main endpoints over real HTTP, as each QA role: status codes, the `{success, message, data}` envelope, RBAC, branch scoping, idempotency, the rate limiter | ~40 s |
| Browser e2e | `VMMS_WEB/e2e/` | The portal's critical journeys in Chromium; fails on any page error or 5xx | ~2 min |
| Load test | `loadtests/locustfile.py` | Hot read/write paths under concurrency, with a p95/error/5xx gate | 3–5 min |

All three run against the **local default tenant only** (`tenant_default`)
and never create another tenant. Everything they create is named `QA ...`,
so `reset_qa_data.py` can remove it.

Run the suites one at a time, and never while `pytest` is running. `pytest`
shares the dev Redis, and its in-process client appears as `127.0.0.1`, so
it uses up the same rate-limit counters the runner hits.

## One-time set-up

```bash
ddev start
ddev exec uv run python scripts/upgrade_all_tenants.py        # after any tenant migration
ddev exec uv run python scripts/qa_regression/seed_qa_fixtures.py
```

The seeder is idempotent. It upserts by natural key, so re-running it
changes nothing. It creates:

- **Users** (all `@example.com`): `qa.reception`, `qa.security`, `qa.host`,
  `qa.approver` (a host), `qa.norole`, and `qa.branchb` (Reception on QA-B
  only). The admin is the dev seed's `admin@example.com`.
- **Superadmin:** `qa.super@example.com`.
- **Branches:** MAIN, QA-B, and QAFB (form-builder writes only).
- **Categories:** `QA_SINGLE` (just the step-0 ownership step) and
  `QA_MULTI` (Reception, then Host).

Tokens: staff can't password-login (they use SSO), so every suite uses
minted tokens. Mint them before each session; they last at most 6 h:

```bash
ddev exec uv run python scripts/qa_regression/mint_tokens.py   # -> var/qa/tokens.json (gitignored)
```

## API regression runner

```bash
ddev exec uv run python scripts/qa_regression/run.py [--only invitations,auth] [--skip-rate-limit]
```

- **Output:** a table per router tag, every failure with its request id,
  and `var/qa/api-results.json`.
- **Fails (exit 1) when:**
  - a call returns a 5xx or an unexpected status,
  - a JSON body isn't the envelope,
  - a router tag in the live `/openapi.json` has no passing happy-path call.
- **Known issues:** `KNOWN_ISSUES` in `run.py` lists calls tied to triaged,
  non-blocker findings. They print as `KNOWN Fx` instead of failing. Once
  one passes, the runner prints it as `STALE`; remove that entry.
- **Rate limits:** login and the SSO endpoints allow 3 calls a minute per
  IP. A full run therefore waits until a minute has passed since the last
  full run finished.

## Browser e2e (VMMS_WEB)

The suite needs `npm run dev` (Vite on :5173, which proxies `/api` to DDEV),
plus freshly minted tokens.

```bash
cd ../VMMS_WEB
npm run e2e:image        # once: builds vmss-e2e:local from the Playwright image
npm run e2e              # all journeys
npm run e2e -- -k lifecycle -x
```

- **Tokens:** they're read from `../VMSS_API/var/qa/` (override with
  `E2E_TOKENS_DIR`).
- **Visitor OTP:** the visitor journey reads its code from the local
  Mailpit (`E2E_MAILPIT_URL`, default `https://vmss-new-api.ddev.site:8026`).
- **Failures:** screenshots and traces go to `VMMS_WEB/e2e/e2e-results/`.
  Open a trace with `npx playwright show-trace <file>`.
- **Known issues:** journeys marked `@pytest.mark.known_issue("Fx")` are
  strict xfails. If one starts passing, the run fails, so remove the
  marker.

## Load test

The per-IP rate limits make a single-machine load test measure the limiter,
so turn them off for the run only:

1. In your local `.env`, set `RATE_LIMIT_ENABLED=false`, and `APP_DEBUG=false`
   (the debug SQL echo alone costs about 10% of throughput).
2. Start a prod-like server next to the dev one. The dev server's `--reload`
   watcher eats a full core.

   ```bash
   ddev exec bash -c 'APP_DEBUG=false RATE_LIMIT_ENABLED=false nohup uv run uvicorn \
       vmss_api.main:app --host 127.0.0.1 --port 8001 > var/qa/uvicorn-8001.log 2>&1 &'
   ```
3. Run the load test:

   ```bash
   ddev exec uv run locust -f loadtests/locustfile.py --headless --host http://localhost:8001 \
       --users 50 --spawn-rate 10 --run-time 5m --csv var/qa/load
   ```

   It prints `LOAD GATE PASS|FAIL` and exits non-zero when the aggregate
   p95 is 500 ms or more, the error rate is 1% or more, or any 5xx
   occurred. Override the limits with `LOAD_P95_LIMIT_MS` and
   `LOAD_ERROR_RATE_LIMIT`. Locust also accepts user class names, for
   example `... StaffUser PublicUser` for a read-only run.
4. Clean up: stop the 8001 server, restore `.env`, and confirm the limiter
   is back (the runner's `rate-limit` case returns 429).

The user mix:

- `StaffUser` ×3: lists and dashboards.
- `ReceptionUser` ×2: create, approve, gate check-in, check-out.
- `PublicUser` ×1: tracking lookup and visit-info options.

A 5-minute run at 50 users creates about 5,000 `QA LOAD` invitations, and
Celery sends their emails to Mailpit.

## Resetting QA data

```bash
ddev exec uv run python scripts/qa_regression/reset_qa_data.py          # dry run: prints the count
ddev exec uv run python scripts/qa_regression/reset_qa_data.py --yes
```

This deletes invitations whose primary contact is named `QA ...`, and their
approval steps, QR codes, vehicles and visitors, in `tenant_default` only.
Audit logs are append-only and stay. Run the runner afterwards if you want a
fresh set of QA invitations for manual browser QA.

## Known pre-existing pytest failures

The full suite has had about 250 failures since mid-October 2026. None of
them are product regressions:

- **About 120:** `MissingGreenlet`. `get_tenant`'s registry-session rollback
  expires objects in the one session the `client` fixture shares with the
  app.
- **About 85:** test payloads missing `visitDetails.branchId`.
- **A handful:** stale test data (dict `consents`, an `IdProofType` import).

Diff a change's failures against a clean-HEAD baseline (see the QA report)
rather than reading the raw count.
