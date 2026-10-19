## Context

See proposal.md for the motivation. Current state that shapes the approach:

**API**
- About 20 feature packages each have `tests.py`, and they run against the real
  `vmss_test` Postgres. `scripts/test.sh` wraps `pytest --cov`. No CI pipeline runs
  it.
- The full-suite baseline is noisy. It has known pre-existing failures:
  - since `0c4d1c1`, `get_tenant`'s rollback in the shared test session raises
    `MissingGreenlet` in about 145 auth and invitations tests,
  - FK flakiness under the full run,
  - factory RNG flakes.

  Concurrent pytest processes race on the shared global schema.

**Portal (VMMS_WEB)**
- React 19 + Vite. There is no test runner.
- `scripts/screenshot-pages.py` already drives Playwright (Python) in the
  `mcr.microsoft.com/playwright/python:v1.55.0-noble` image, over
  `--network host` against Vite on :5173. Vite proxies `/api` to DDEV.

**Auth constraints for automation**
- Password login is admin-only. Staff roles must use SSO, so automation mints access
  tokens in the container (`core.security`) and injects them as
  `sessionStorage.token`.
- `slowapi` rate-limits public and auth endpoints by IP. A load test from one host IP
  will trip those limits by design.

**Local data**
- Local data lives only in the `tenant_default` schema.
- The earlier `run.py`, `seed_qa_fixtures.py` and
  `reset_default_tenant_invitations.py` were never committed and no longer exist.

**Edit scope**
- The planning home is VMSS_API, but browser tests and UI blocker fixes belong in
  VMMS_WEB, the sibling working directory.

## Goals / Non-Goals

**Goals:**
- One command per suite, each runnable from a clean `ddev start` plus the seeder.
- Deterministic QA data: a `QA ` name prefix, QA categories, and a reset script.
  Suites can then re-run without hand cleanup.
- Fail loudly on 5xx, on an envelope violation, on a browser page error, and on a
  load-threshold breach.
- A triage process that separates new regressions from known pre-existing failures.

**Non-Goals:**
- Wiring the suites into the Azure/OpenStack CI pipelines (follow-up change).
- Load-testing production or staging, or capacity planning for production sizing.
- Fixing every pre-existing pytest failure. Only those that turn out to mask a real
  product blocker are in scope. The `get_tenant` test-session rollback issue is
  logged as a non-blocker, because it is test infrastructure, unless triage shows a
  product impact.
- Cross-browser matrix. The suite runs Chromium only, and mobile-width layout is
  already covered by `screenshot-pages.py`.
- Malware scanning, pen-testing, or a security audit beyond RBAC and branch and
  tenant scoping checks.

## Decisions

### D1. API regression runner: a standalone httpx script, not more pytest
**What:** `scripts/qa_regression/run.py` runs inside the DDEV web container. It calls
the live API at `http://localhost:8000/api/v1` over HTTP and uses minted tokens per
QA role.

**Why not pytest:** the pytest suite already covers per-feature logic. Its
shared-session fixture also hides real-session bugs, such as the `get_tenant`
rollback, because tests route `get_db` and `get_tenant_db` to the same session. The
runner exercises the real middleware, sessions, Redis and Celery wiring that
production uses.

**How the call list is built:** it is declarative: a list of
`(router_tag, method, path, role, payload_builder, expected_status)` entries.

**Coverage check:** coverage is checked against the live `/openapi.json` route
list. Any router tag with no entry fails the run, which is what the "unknown router
is flagged" scenario requires. This mirrors how
`test_every_feature_router_is_registered_in_api_router` discovers routers rather than
trusting a maintained list.

**Output:** a JSON results file, plus a console table, under `var/qa/`. `var/qa/`
is gitignored, and the report quotes a summary from it.

### D2. Fixture seeder and reset are separate scripts
**What:**
- `scripts/qa_regression/seed_qa_fixtures.py` upserts by natural key (email, branch
  code, category code), so re-runs change nothing.
- `scripts/qa_regression/reset_qa_data.py --yes` deletes only QA-prefixed
  invitations and visitors.

Both refuse any schema other than `tenant_default`.

**Why:** the user's standing rule is that only the default tenant exists locally,
and all QA data lives there. Separate reset tooling lets QA data be removed without
touching the admin's other data.

**Alternative rejected:** a throwaway QA tenant. It would violate the
single-default-tenant rule.

### D3. Browser e2e: Python Playwright with pytest, in VMMS_WEB `e2e/`
**What:** use `pytest-playwright` inside the same Playwright Docker image as
`screenshot-pages.py`. Build the image once (`vmss-e2e:local`) and run it with
`--user $(id -u):$(id -g) -e HOME=/tmp`, to avoid root-owned output and the blocked
`pip install` in a `bash -c` command. `npm run e2e` wraps the `docker run`.

**Why Python and not `@playwright/test` (Node):**
- It reuses the existing image and tooling pattern.
- It adds no new node devDependencies or browser download to the web repo.
- Token minting is already a Python step.

The trade-off is that frontend developers get a Python test suite. That is
acceptable, because the suite is black-box.

**Fixtures:**
- A `role_page(role)` fixture injects the minted token into `sessionStorage` before
  navigation. Tokens are minted once per run by a helper the API repo provides
  (`scripts/qa_regression/mint_tokens.py` writes `var/qa/tokens.json`), and passed
  through an env var or a mounted file.
- An autouse fixture attaches `page.on("pageerror")` and
  `page.on("response", status>=500)` collectors. It fails the test on teardown and
  saves a screenshot and a trace under `e2e-results/`, which is gitignored.

**Selectors:** use role, label and text selectors (`get_by_role`, `get_by_label`).
`data-testid` attributes are added only where no accessible selector exists. Adding
one is a non-functional UI edit.

### D4. Load test: Locust, headless, token-minted users
**What:** `loadtests/locustfile.py`, with `locust` added as a uv dev dependency. It
runs headless from the DDEV web container against `localhost:8000`, with
`--users 50 --spawn-rate 10 --run-time 5m --csv var/qa/load`.

**User classes:**
- `StaffUser` (weight 3): dashboards and the invitation list, using filters and
  pagination.
- `ReceptionUser` (weight 2): invitation create on `QA_SINGLE`, approve, check-in,
  check-out. It uses `Idempotency-Key` headers.
- `PublicUser` (weight 1): visit-info lookup with a valid signed token.

**Why Locust over k6:** it is Python, so it shares the token-minting and fixture code
with D1. It needs no extra binary in the container, and it is CSV-friendly for the
report.

**Rate limits:** login is not load-tested through the password endpoint. Users start
with pre-minted tokens, because login is rate-limited by design, and hammering it
from one IP measures the limiter, not the system. The public lookup is limited per
IP as well. For the load run only, the limiter is raised through a `.env` override
(for example `RATE_LIMIT_ENABLED` or per-route limits, whichever settings exist).
The report states this explicitly, along with the limiter's own correct 429
behaviour, which is checked separately by one API runner case.

**Threshold check:** a Locust `events.quitting` hook enforces the gates in the spec:
p95 < 500 ms, error rate < 1%, zero 5xx. When a gate is breached, it sets
`environment.process_exit_code = 1`.

**Celery:** the stack runs Celery during the load test (DDEV's worker), so enqueue
paths (notifications) are exercised. Email goes to the local mail catcher, and no
real provider is used.

### D5. Triage against a baseline worktree
**What:**
1. Run pytest once on a clean-HEAD worktree (`git worktree add --detach .baseline-wt
   HEAD`, with `.env` copied in; never `git stash`, which also stashes `.env`).
2. Run it once on the working tree, sequentially and never concurrently.
3. Diff the two failure sets.
   - A failure present only in the working run is a regression.
   - Pre-existing failures are triaged individually against the blocker definition
     in the spec. A pre-existing failure can still be a blocker if it reflects a
     real product bug.

**Why:** memory shows that several past "regressions" were pre-existing noise, and
re-diagnosing them each time wastes the QA pass.

### D6. Blocker fixes: in-change, one commit each, spec-preserving
**What:** each blocker gets its own `fix:` commit with a regression test at the
lowest sensible level:
- pytest for an API bug, including the permission-denied and tenant-isolation tests
  when the bug touches RBAC or scoping,
- an e2e assertion for a UI bug.

The commit is recorded in the findings report.

**Splitting rule:** if a fix would change a requirement in an existing
`openspec/specs/*` capability, or change an API contract (a breaking change under
`api-conventions.md` §2), it is not done here. It is logged as a blocker with a named
follow-up change, and the verdict stays "blockers open" until that change lands.

**Why:** this keeps this change's spec delta limited to the harness, and avoids
smuggling contract changes into a "QA" change.

### D7. Report location and shape
**What:** `docs/qa/2026-10-full-stack-qa.md`, dated by run. It contains:
- the environment (commit SHAs of both repos, and the DDEV service versions),
- the per-suite summary,
- the load baseline table (p50, p95 and p99 per endpoint),
- the findings table (id, suite, severity, repro, status, and the fixing commit or
  follow-up),
- the verdict.

`docs/features/qa-harness.md` documents how to run each suite.

## Risks / Trade-offs

- **[Risk] Load and browser runs create many QA rows in the default tenant**, which
  the admin also uses for manual QA. → Mitigation: the `QA LOAD` prefix and QA
  categories; `reset_qa_data.py` runs after the load test; the reset is scoped by
  prefix, never a blanket delete.
- **[Risk] Local WSL2 and DDEV performance is not representative**, so p95 may be
  noisy or breach on slow I/O. → Mitigation: the numbers are a recorded baseline. A
  breach is first re-run once, then profiled (py-spy against a prod-like server
  without `--reload`). Decided during apply (2026-10-16): a latency-only breach on
  the local stack is recorded with its capacity curve and handed to a follow-up
  performance change; only error-rate or 5xx breaches on core endpoints are
  blockers.
- **[Risk] Raising rate limits for the load run could be left on.** → Mitigation:
  the override lives only in a documented `.env` toggle reverted at the end of the
  task. The `.env` file is never staged (git-workflow §5), and the API runner
  re-checks that the limiter returns 429 after the revert.
- **[Risk] Tokens minted with a long TTL for test runs could leak.** → Mitigation:
  they are written only to the gitignored `var/qa/` and minted against local
  `tenant_default`. The TTL is limited to the run, at most 6 h.
- **[Risk] Flaky e2e from the async UI.** → Mitigation: rely on Playwright
  auto-waiting and web-first assertions, with no fixed sleeps. Any test that fails
  intermittently is rerun before it is reported as a finding (as with the known avatar
  and second-boundary flake).
- **[Trade-off]** The browser suite is Chromium-only, with a curated journey list,
  not exhaustive page coverage. Breadth comes from `screenshot-pages.py`. Depth on
  critical flows comes from e2e.

## Migration Plan

Additive tooling only, so no deploy step is needed. Rollback is deleting the new
directories and the `locust` dev dependency. Blocker fixes ship as ordinary commits
on `feature/suggestions-fix` and can be reverted individually.

## Open Questions

- Should a smoke subset of the API runner later gate the dev pipeline? This is
  deferred to the CI follow-up change, and does not affect this change's harness
  design.
