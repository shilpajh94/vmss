## Context

See `proposal.md` - Why for the full audit summary and its Correction note.
This document originally scoped three fixes; re-verification during
`/opsx:apply` showed the first was based on a misdiagnosis, so it's recorded
here for the record rather than implemented.

1. **Corrected finding — test-suite non-determinism.** The initial audit (five
   review passes run *concurrently* against one shared `vmss_test` database)
   reported per-feature-file flakiness:
   - `auth/tests.py`: `test_login_success` / `test_tenant_schema_isolation`
     erroring with `ForeignKeyViolationError` on `audit_logs_actor_user_id_fkey`.
   - `org_structure/tests.py`: flaky `StaleDataError`/FK errors between runs.
   - `platform/tests.py` / `reports/tests.py`: `UniqueViolationError`/
     `ForeignKeyViolationError` against global-schema tables.
   - `invitations/tests.py`: FK violations when run standalone.

   Re-verification found none of this reproduces under serial execution: 17
   consecutive runs (every feature file standalone, several times each, full
   suite twice) were all green. Running `platform`, `reports`, and `auth`
   tests **concurrently** (three `pytest` processes at once) reproduced the
   exact failure signatures immediately. The actual defect:
   `conftest.py`'s `_TENANT_SCHEMA = "tenant_acme_test"` and the `tenant`
   fixture's fixed `slug="acme-test"` are process-wide constants written into
   `global.tenants` (unique on `schema_name`) and `global.tenant_user_index`
   — two concurrent `pytest` processes each try to insert/reference the same
   global rows and collide. This is a concurrency-safety gap in the test
   fixtures, not a background-write/session-handling bug, and it doesn't
   affect `git-workflow.md` §4's CI gate (one `pytest` process). **No fix is
   scoped for it in this change** — see Decisions below.

2. `POST /invitations` (API-09) has no `Idempotency-Key` handling, while
   `POST /invitations/{trackingToken}/register` (API-10) already implements
   the exact pattern needed, in the same file
   (`invitations/router.py::_cached_response`/`_cache_response`,
   Redis-backed, 24h TTL, keyed
   `vmss:{tenant_id}:invitations:idempotency:{key}`).

3. `GET /invitations/track` declares
   `response_model=Envelope[InvitationTrackingOut]` for both of its lookup
   modes, but the email-lookup branch actually returns
   `list[InvitationTrackingSummaryOut]` — a different, narrower shape.

## Goals / Non-Goals

**Goals:**
- Close the two concrete API-09/API-12 contract gaps with the smallest change
  that reuses patterns already proven correct elsewhere in the same file.
- Leave a clear, correct record of the test-suite investigation so a future
  reader doesn't re-diagnose the same false lead.

**Non-Goals:**
- Making the test suite safe under *concurrent* `pytest` invocations
  (Decision 1's deferred item). `git-workflow.md` §4's CI gate runs the suite
  as one process, which is already reliably green; hardening for concurrent
  local runs is a separate, opt-in improvement, not a compliance gap.
- Redesigning the background-audit-log or Celery-eager-task architecture.
  Both were suspected during the initial (mis-)diagnosis and are confirmed
  correct as written.
- Building the API-06 approval-rule evaluation engine or an API-11 SMS
  gateway (see proposal.md's Non-goals).

## Decisions

### Decision 1: Do not change `conftest.py` for test determinism — the suite is already deterministic where it needs to be

No code change. Serial execution (single `pytest` process — every feature
file standalone, several repeats each, and the full suite twice) was
confirmed reliably green. The only reproducible failure mode requires
running multiple `pytest` processes concurrently against the shared
`vmss_test` database, which is not how `git-workflow.md` §4's CI gate runs the
suite, and not a realistic local workflow either (`scripts/test.sh` invokes
one process). Spec.md's "Deterministic Test Suite Execution" requirement is
satisfied by current behavior; its scenarios were re-validated against real
runs rather than assumed.

**Alternative considered**: harden `conftest.py` against concurrent execution
anyway (e.g., suffix `_TENANT_SCHEMA`/tenant slug with a per-process id) as a
defensive improvement. Deferred rather than rejected outright — flagged as a
follow-up if this team ever adopts `pytest-xdist` or routinely runs suites in
parallel; not worth the churn to fix a mode nothing currently exercises.

### Decision 2: Extend the existing Idempotency-Key helper to invitation creation

Reuse `invitations/router.py`'s existing `_cached_response`/`_cache_response`
helpers (already proven for API-10) on `POST /invitations`, keyed the same way
(`vmss:{tenant_id}:invitations:idempotency:{key}`, `api-conventions.md` §3).
No new Redis convention, no new library — this is a call-site addition, not a
new mechanism.

**Alternative considered**: a shared FastAPI dependency/decorator for
idempotency, usable by any future mutating endpoint. Rejected for this change
as scope creep — worth proposing separately once a third endpoint needs it;
today only two endpoints in one file need this behavior, and duplicating a
call is cheaper than an abstraction with two call sites (per this project's
own bias against premature abstraction).

### Decision 3: Make the track endpoint's response_model a discriminated union of its two real shapes

Change `GET /invitations/track`'s `response_model` to
`Envelope[InvitationTrackingOut | list[InvitationTrackingSummaryOut]]`,
matching exactly what the two lookup branches already return. No change to
either branch's actual runtime response — this only corrects the documented
contract per `api-documentation.md` §1.

**Alternative considered**: split into two separate endpoints
(`/invitations/track/by-id`, `/invitations/track/by-email`). Rejected —
that's an API shape change requiring client updates and versioning
consideration (`api-conventions.md` §2) for a problem that's purely a
documentation-accuracy defect, not a functional one.

## Risks / Trade-offs

- [Risk] Declaring the test suite "deterministic enough" based on 17 serial
  runs doesn't prove it can never flake — it's evidence, not a proof →
  Mitigation: the concurrency root cause is now understood and documented, so
  if a future flake does appear, `_TENANT_SCHEMA`/tenant-slug collision under
  concurrent execution is the first thing to check before re-diagnosing from
  scratch.
- [Trade-off] The track endpoint's `Union` response_model is honest but less
  ergonomic for typed client generation than two separate schemas would be →
  accepted, since it matches this project's non-goal of avoiding an API shape
  change for a docs-only fix.

## Migration Plan

- No data migration. No new dependencies. No `.env`/`settings` changes. No
  `conftest.py` changes.
- Deploy order is irrelevant to production traffic: the two `invitations`
  fixes are additive (optional header) or documentation-only (response_model),
  so there is nothing to sequence or roll back beyond a normal PR revert.
