## Why

The user asked to verify the already-delivered implementation against:

> API-07 · Admin/Platform · Branch/location provisioning & cross-branch
> reporting rollup
>
> API-08 · Platform · OpenAPI schema, versioning, and rate limiting
> middleware

with proper test-case validation.

Unlike the last two audits (`archive/2026-08-18-harden-org-structure-crud`,
this session's `harden-visitor-types-crud`), this one found **no functional
defects**. Both APIs are correctly implemented, well-layered, and covered
by real tests against Postgres. What it did find is a verification gap: two
of the three rate-limited authentication/provisioning endpoints have never
actually had their rate limit exercised by a test, even though the exact
proven pattern for doing so already exists elsewhere in this codebase — and
none of the three capabilities this work spans (bulk branch provisioning,
the cross-branch rollup, rate limiting) has a baseline spec captured yet.

**Audit result:**

| API | Requirement | Verdict |
|---|---|---|
| API-07 | Branch/location provisioning | **Compliant** — `POST /branches/provision` (`org_structure/service.py::provision_branch`) bootstraps a whole Branch → Building → Floor → Department/ReceptionDesk/SecurityGate tree in one transaction, with per-request and against-database duplicate-code checks, gated by its own `branches:provision` permission. Already hardened this session (`harden-org-structure-crud`'s partial-unique-index + `IntegrityError→409` fix applies to this endpoint too). |
| API-07 | Cross-branch reporting rollup | **Compliant** — `GET /reports/branches/rollup` aggregates building/floor/department/desk/gate/active-employee counts per branch via grouped-by-branch queries (no per-branch loop, `query-performance.md` §2), correctly reports a zero row for a branch with nothing under it, and is tenant-isolation-tested at the repository level even though it's a cross-model join rather than a single repository's `get()`. |
| API-08 | OpenAPI schema | **Compliant** — every registered router's routes are discoverable in the schema (enforced by an automated test, not a maintained list), protected routes declare `HTTPBearer` security, response schemas render camelCase, and `/docs`/`/redoc`/`/openapi.json` are correctly gated off in production. |
| API-08 | Versioning | **Compliant** — exactly one version (`/api/v1`) exists today, consistent with `api-conventions.md` §2's "no version bump needed until an actual breaking change." Nothing to test beyond what already exists, since there's no v2 to test against. |
| API-08 | Rate limiting middleware | **Compliant, but under-verified.** `slowapi`'s `Limiter` is correctly wired (`core/rate_limit.py`, registered in `main.py`, `@limiter.limit(...)` applied to `POST /auth/login` (5/min), `POST /platform/auth/login` (5/min), and `POST /platform/tenants` (3/min)) — but **zero tests** exercise any of these three. `invitations/tests.py` already has the exact pattern needed (`test_self_register_rate_limit_trips`, `test_track_rate_limit_trips`: monkeypatch `limiter.enabled = True` for one test, fire enough requests to trip the limit, assert a 429 appears), proven correct for two other rate-limited endpoints — it just was never applied to these three. |

**How this was verified**: read every rate-limited router (`auth/router.py`,
`platform/router.py`, `invitations/router.py`) and confirmed via
`grep -rn "limiter.limit"` that five call sites exist codebase-wide;
cross-referenced against `grep -rn "429\|RateLimitExceeded"` across every
`tests.py` and found only `invitations/tests.py` exercises the 429 path —
`auth/tests.py` and `platform/tests.py` have none. Ran
`tests/test_api_documentation.py`, `reports/tests.py`, and `platform/tests.py`
directly (20 passed) to confirm the OpenAPI/versioning/rollup pieces are
solid as-is.

## What Changes

- Add `test_login_rate_limit_trips` to `auth/tests.py`, mirroring
  `invitations/tests.py::test_track_rate_limit_trips`'s
  `monkeypatch.setattr(limiter, "enabled", True)` pattern, against
  `POST /auth/login`.
- Add `test_platform_login_rate_limit_trips` and
  `test_create_tenant_rate_limit_trips` to `platform/tests.py`, same
  pattern, against `POST /platform/auth/login` and `POST /platform/tenants`
  respectively.
- **No production code changes** — the rate-limiting implementation is
  already correct; this closes a test-verification gap only.
- Capture baseline specs for the three capabilities this audit touched that
  don't have one yet: `reports` (the cross-branch rollup), `rate-limiting`
  (the middleware, now with complete endpoint coverage), and a `MODIFIED`
  addition to the existing `org-structure` baseline for bulk branch
  provisioning specifically (today's `org-structure` spec covers per-entity
  CRUD but not the `POST /branches/provision` bulk-bootstrap capability).

## Capabilities

### New Capabilities
- `reports`: the cross-branch structural rollup (API-07's reporting half).
- `rate-limiting`: the `slowapi`-backed rate-limiting middleware and which
  endpoints it protects (API-08's rate-limiting third).

### Modified Capabilities
- `org-structure`: adds a "Bulk Branch Provisioning" requirement for
  `POST /branches/provision` — present in the code and tested since before
  this session, but not yet captured in the capability's baseline spec
  established in `archive/2026-08-18-harden-org-structure-crud`.

## Impact

- **Code**: `src/vmss_api/auth/tests.py`, `src/vmss_api/platform/tests.py`
  (3 new tests total). No non-test files change.
- **No breaking changes**: purely additive test coverage.
- **Out of scope**: extending the same rate-limit-trip test pattern to any
  future rate-limited endpoint is a standing convention now, not a
  one-time backfill — no code change enforces it, since `security-architecture.md`
  §2 already states the requirement and this change's tests are the
  reference examples to copy going forward.
