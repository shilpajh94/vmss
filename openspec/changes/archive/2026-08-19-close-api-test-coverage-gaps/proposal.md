## Why

API-01 through API-14 are already implemented (`auth`, `org_structure`, `visitors`,
`platform`, `core`, `invitations`, `registrations`, `reports`), and most of them already
carry strong test coverage per `testing-standards.md` §2 (happy path, permission-denied,
tenant-isolation). A full audit against that bar found the suite is not uniformly complete:
a handful of endpoints and one cross-cutting concern (rate-limit response shape) have no
test proving a specific spec'd behavior, and one real bug — an orphaned-file-upload defect
in `invitations/service.py` — surfaced while reading the code for gaps. This change closes
the specific coverage gaps the audit identified and fixes the one bug found, rather than
rewriting or duplicating the already-solid coverage that exists.

## What Changes

- **auth (API-01/02) — bug fix**: add the missing test for `sync_employee_directory`'s
  duplicate-employee-code/email-within-batch 409 path (`auth/service.py:376-380`) — only the
  unknown-department-404 branch of that endpoint is currently tested. Writing this test
  surfaced a real bug: `create_user` (called per new item inside the sync loop) flushes
  internally, so a duplicate `employee_code`/email raised `IntegrityError` *during the loop*,
  before reaching the `try/except` that only wrapped the final `commit()` — the intended 409
  never fired; the request 500'd instead. Fixed by wrapping the whole loop, not just the final
  commit, in the `try/except IntegrityError` block.
- **visitors (API-05/06)**: add permission-denied tests for `list`/`get`/`delete` on
  `VisitorCategory` and `ApprovalWorkflowRule` (currently only `create`/`update` are proven
  to reject an unpermitted caller).
- **platform (API-07)**: add a deterministic test for `POST /platform/tenants` returning 409
  on a duplicate slug — today that path is only asserted as an incidental side effect of the
  rate-limit test (`status_code in {409, 429}`), which doesn't pin down which behavior fired.
- **core/API-08 (rate limiting + OpenAPI)**: add a test proving a tripped rate limit's 429
  response body matches the standard `error_response` envelope (`success: false` + a
  `message`), per `openspec/specs/rate-limiting/spec.md`'s third requirement — today every
  rate-limit test asserts only the status code, never the body shape, so a regression there
  would go undetected.
- **registrations (API-13/14)**: add an HTTP-boundary smoke test on `POST
  /registrations/walk-in` for disguised-file-type and oversized-file rejection. The
  validation logic itself is already tested via the shared `invitations.service` code path;
  this closes the gap at the registrations router's own boundary.
- **reports**: extend the cross-branch rollup happy-path test to assert
  `security_gate_count` — the fixture never created a security gate, so that rollup field
  has never been exercised by an assertion.
- **invitations (API-09/11/12) — bug fix**: `create_invitation` currently uploads each
  visitor's ID-proof file to storage inside the per-visitor validation loop, before the
  invitation row is committed. If a later visitor's file fails content/type validation, the
  earlier visitors' files are already persisted to storage with no compensating cleanup —
  a rejected group invitation can leave orphaned blobs behind. Fix: validate every file's
  content/type up front, before persisting any of them, so a rejected submission never
  writes to storage at all.
- **Housekeeping note (not part of this change's code diff)**: the audit found three
  existing unarchived changes (`add-pre-registration`, `harden-invitation-tracking-fidelity`,
  `document-invitation-create-payload-shape`) whose proposed work already appears to be
  implemented in the current code — `add-pre-registration`'s description of a separate
  self-registration endpoint is stale (later collapsed into single-call `POST /invitations`
  by an already-archived change). These should be archived or updated separately; this
  change does not touch them.

### Explicitly out of scope

- `invitations/rbac_catalog.py` grants `invitations:view`/`invitations:cancel` to
  reception/host/admin, but no endpoint currently checks or exposes either action — a
  design gap (missing list/cancel endpoints), not a test gap or a bug. Building those
  endpoints is new feature scope beyond API-09/11/12 as specified; this change does not
  add them. Flagged in `design.md` as an open question for a future change.
- `registrations/deps.py`'s O(n) device-key lookup loop (necessary because Argon2 hashes
  aren't indexable) is a documented, deliberate tradeoff for an expected-small device-key
  set, not a bug — left as-is.
- `org_structure` already meets or exceeds the §2 bar for every one of its 36 endpoints;
  no changes proposed there.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `invitations`: `create_invitation` must not persist any visitor ID-proof file to storage
  when the submission as a whole is rejected — validation of every file happens before any
  file is written, not interleaved per-visitor.

## Impact

- **Modified code**: `src/vmss_api/invitations/service.py` (`create_invitation` — reorder
  validation ahead of storage writes); `src/vmss_api/auth/service.py`
  (`sync_employee_directory` — widen the `IntegrityError` try/except to cover the whole
  loop, not just the final commit).
- **Modified/added tests**: `src/vmss_api/auth/tests.py`, `src/vmss_api/visitors/tests.py`,
  `src/vmss_api/platform/tests.py`, `src/vmss_api/registrations/tests.py`,
  `src/vmss_api/reports/tests.py`, `src/vmss_api/invitations/tests.py` (orphaned-upload
  regression test), and either `src/vmss_api/core/tests.py` or
  `tests/test_api_documentation.py` for the rate-limit envelope-shape test (per the audit,
  the latter is already the home for cross-cutting API-08 assertions).
- **No schema/migration changes.** No new dependencies. No breaking changes — every change
  either adds a test or fixes an internal ordering bug with no external contract change.
