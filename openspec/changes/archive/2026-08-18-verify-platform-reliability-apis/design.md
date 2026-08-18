## Context

See `proposal.md` - Why for the full audit. Unlike the prior two audits in
this session, there is no defect to fix here — the only actionable item is
adding the three missing rate-limit-trip tests, using a pattern that already
exists and is already proven correct (`invitations/tests.py`). This
document covers why that pattern transfers as-is, and how the three new
baseline/delta specs are scoped.

## Goals / Non-Goals

**Goals:**
- Prove, not just assert from reading the decorator, that `/auth/login`,
  `/platform/auth/login`, and `/platform/tenants` actually enforce their
  rate limits and return 429 once tripped.
- Capture baseline specs for `reports` and `rate-limiting` (neither exists
  yet), and close the one real gap in the `org-structure` baseline
  (bulk provisioning wasn't captured when that baseline was written).

**Non-Goals:**
- Changing the rate limits themselves (5/min, 5/min, 3/min) — the audit
  found no reason to think any of these three values is wrong.
- Building a shared/parametrized rate-limit-test helper across features.
  Three call sites (soon five, counting the two `invitations` already has)
  copying an ~8-line pattern is cheaper than introducing a fixture/helper
  two features would need to adopt for a change scoped to closing a
  verification gap — worth revisiting if a sixth rate-limited endpoint
  shows up.

## Decisions

### Decision 1: Reuse the exact `invitations/tests.py` rate-limit-trip pattern verbatim

Each new test: log in (or, for `/auth/login` itself, skip login — the
endpoint being tested *is* login), `monkeypatch.setattr(limiter, "enabled",
True)`, fire enough requests in a loop to exceed the configured per-minute
limit, assert `any(r.status_code == 429 for r in responses)`. No new
fixtures, no new helper — copy the shape already proven twice in
`invitations/tests.py`.

**Alternative considered**: mock `slowapi` internals directly (e.g. patch
the limiter's internal counter) to avoid actually sending N requests per
test. Rejected — the existing, already-merged pattern sends real requests
against the real (test-database-backed) app and is simple to read; a
lower-level mock would test slowapi's internals instead of this
application's wiring of it, which is the thing actually worth verifying.

### Decision 2: Three new/modified capability specs, scoped to what this audit actually touched

Add `reports` and `rate-limiting` as new capabilities (neither has ever had
a baseline spec), and add one `MODIFIED` requirement to the existing
`org-structure` baseline for bulk branch provisioning — a real, tested,
already-shipped capability that simply wasn't included when that baseline
was written during `harden-org-structure-crud`.

**Alternative considered**: fold `rate-limiting` into the existing
`api-documentation` capability, since both are cross-cutting HTTP-layer
concerns. Rejected — `api-documentation`'s own Purpose statement is scoped
specifically to "how the OpenAPI schema and Swagger/ReDoc UI are exposed,
secured, and kept in sync," which rate limiting has nothing to do with;
stretching that capability's scope to cover an unrelated middleware would
make its own spec harder to read, not easier.

## Risks / Trade-offs

- [Risk] Firing 10-25 requests per new test adds a small amount of runtime
  to `auth/tests.py`/`platform/tests.py` (each request still round-trips
  through the real test app/DB) → accepted, matching the cost the existing
  `invitations` rate-limit tests already pay; not large enough to matter at
  this suite's current size (171 tests, ~40s).
- [Trade-off] `monkeypatch.setattr(limiter, "enabled", True)` mutates
  process-wide shared state (`core/rate_limit.py`'s module-level `limiter`
  singleton) for the duration of one test — `pytest`'s `monkeypatch`
  fixture reverts it automatically at teardown, same safety net the two
  existing `invitations` tests already rely on, so this isn't a new risk.

## Migration Plan

- No code, schema, or dependency changes. Test-only, plus documentation
  (three new/modified `openspec/specs/` capability files).
