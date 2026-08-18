## Why

The user asked for a compliance check of all 12 API items already delivered across
Auth & Access, Org Setup, Visitor Types, Admin/Platform, and Pre-Registration
against their stated requirements, this repo's coding-standard rule files
(`.claude/rules/*.md`), input-validation expectations, and test-suite health. A
five-way audit (one pass per feature area, each running `ruff`, `mypy`, and
`pytest` against the real DDEV/Postgres stack rather than reading code alone)
found the architecture, layering, and RBAC/tenancy model are sound end to end,
but surfaced three concrete, fixable defects and one already-documented,
out-of-scope gap that the user should see decided explicitly rather than left
implicit.

**Audit result per item:**

| API | Area | Verdict |
|---|---|---|
| API-01 | JWT auth + branch-scoped access context | Compliant |
| API-02 | RBAC scoped per branch | Compliant |
| API-03 | Company/Branch/Building/Floor/Department CRUD | Compliant |
| API-04 | Reception Desk/Security Gate/Employee sync | Compliant |
| API-05 | Visitor Category + configurable form schema | Compliant |
| API-06 | Approval workflow rules per category | **Partial** — CRUD is complete and correct, but no rule-*evaluation* engine exists yet (`approvals/` package was never created); the code's own docstrings already flag this as a future feature, not a hidden gap |
| API-07 | Branch provisioning + cross-branch rollup | Compliant |
| API-08 | OpenAPI schema, versioning, rate limiting | Compliant |
| API-09 | Create invitation (single/group) + tracking ID | **Partial** — missing the `Idempotency-Key` mechanism `api-conventions.md` §3 requires for this exact endpoint |
| API-10 | Public multi-step self-registration | Compliant |
| API-11 | Email/SMS + QR dispatch on submission | **Partial** — email + QR path fully wired; SMS sending is an explicit, already-documented open item (no gateway chosen yet) |
| API-12 | Track-request lookup | **Partial** — `response_model` on the endpoint doesn't match the response shape actually returned by its email-lookup branch |

**Correction made during `/opsx:apply`**: the initial audit (five parallel
review passes, run concurrently against one shared `vmss_test` database)
reported `pytest` as non-deterministic per feature file
(`ForeignKeyViolationError`/`StaleDataError` against
`audit_logs`/`tenant_user_index`). Before touching `conftest.py`, this was
re-verified directly: 17 consecutive serial runs (every feature file standalone,
several times each, plus the full suite twice) were all green with zero flakes.
Running three of those same test files *concurrently* against the shared
database reproduced the exact failure signatures immediately. The real defect
is narrower than first diagnosed: `conftest.py` hardcodes one tenant
schema/slug (`tenant_acme_test`/`acme-test`) in global-schema tables with a
unique constraint, so concurrent `pytest` processes collide on it — a
concurrency-safety gap, not a per-request session-handling bug. It doesn't
affect `git-workflow.md` §4's actual CI gate (the suite run as one process),
which is already reliably green. See `design.md`'s Context for the corrected
diagnosis; no code change is scoped for it in this change (see What Changes).

## What Changes

- Verified (no code change): every feature's test file already passes
  reliably, standalone and as part of the full suite, under normal serial
  execution — see the Correction note above. The test suite's lack of safety
  under *concurrent* `pytest` invocations is noted as a separate, deferred
  finding, since it doesn't affect the actual CI gate.
- Add `Idempotency-Key` support to `POST /invitations` (API-09), mirroring the
  Redis-backed pattern already implemented on the self-registration endpoint
  (API-10), so a retried invitation-creation request from a flaky client
  connection cannot create two invitations.
- Fix `GET /invitations/track`'s (API-12) `response_model` so it accurately
  documents both response shapes it can actually return (full detail by
  tracking ID vs. minimal-disclosure summary by email), per
  `api-documentation.md` §1.
- **Non-goal, explicitly deferred**: building the approval-rule *evaluation*
  engine (API-06) and a working SMS gateway (API-11) are both substantial,
  separate features already flagged as open items in the existing code's own
  docstrings/design notes — not bundled into this compliance-hardening change.
  Flagging them here so the decision to defer is explicit rather than silently
  dropped.

## Capabilities

### New Capabilities
- `api-compliance-hardening`: cross-cutting reliability and contract-accuracy
  requirements surfaced by this audit — deterministic test execution
  regardless of run order/isolation, invitation-creation idempotency, and
  track-endpoint response-contract accuracy. Housed as its own capability
  rather than folded into `invitations`' in-flight spec (the still-open
  `add-pre-registration` change already owns that capability's baseline
  requirements) to avoid a spec-path collision between two concurrently open
  changes.

### Modified Capabilities
- None. No existing `openspec/specs/` capability has a baseline spec yet for
  `auth`, `org_structure`, `platform`, `reports`, or `invitations` (only
  `api-documentation` has been archived to date), so there is no existing
  delta target for the fixes above outside the new capability declared here.

## Impact

- **Code**: `tests/conftest.py` (session/engine fixture override for
  background-task and Celery-eager-mode DB access); `src/vmss_api/invitations/router.py`
  and `service.py` (Idempotency-Key handling on invitation creation, reusing
  `core/` Redis helpers already used by the registration endpoint);
  `src/vmss_api/invitations/schemas.py` and `router.py` (track endpoint response
  contract).
- **Tests**: no new test *scenarios* beyond what already exists for
  idempotency/response-contract coverage patterns elsewhere in `invitations`;
  existing `auth/tests.py`, `org_structure/tests.py`, `platform/tests.py`,
  `reports/tests.py`, `invitations/tests.py` should each go from
  order-dependent to reliably green.
- **No breaking changes**: the track endpoint's actual wire response doesn't
  change, only its documented schema; invitation creation gains an optional
  header, not a required one.
- **Out of scope**: API-06's rule-evaluation engine and API-11's SMS gateway
  remain open items for a future, separately-scoped change.
