## Why

The user asked for a full pass confirming every API works — explicitly calling
out the newly implemented ones — with email send/receive, push notifications,
history tracking, and the invitation workflow all checked end to end, not just
assumed from each feature's own unit tests. Three concrete gaps make this due
now rather than a restatement of the prior "verify everything" changes already
archived in this repo (`verify-full-api-and-notification-delivery`,
`verify-sso-and-full-api-suite`, `codebase-review-and-e2e-scenario-test`):

1. **Two APIs landed since the last full-suite audit and have never been
   exercised by the cross-feature workflow tests.** `src/vmss_api/audit_trail/`
   (history-tracking listing/detail + async CSV/PDF report export, committed
   untracked, 17 tests) and invitations' approval-step delegation +
   `relevantToMe` personal worklist (`invitations/router.py`,
   `approvals/service.py::delegate_step`, committed at `01167d8`, 20 tests
   across `approvals/tests.py` and `invitations/tests.py`) both have solid
   per-feature endpoint coverage — happy path, permission-denied, and
   tenant-isolation cases all present, per `testing-standards.md` §2. But
   `tests/test_workflow_full_lifecycle.py`, `tests/test_workflow_staff_admin.py`,
   and `tests/test_workflow_visitor.py` — the tests that simulate a real,
   multi-feature visitor/staff journey end to end — mention none of
   `delegat`, `relevant`, `audit_trail`/`audit-trail`, or push notifications
   anywhere in their ~1,300 lines. Push notifications specifically have existed
   since `ea84555` (`feat: add push notifications for staff on
   invitation/approval lifecycle events`), well before these workflow files
   were last touched, so this is not a brand-new gap the delegation feature
   introduced — it is a pre-existing hole the "newly implemented APIs" ask
   surfaces now.
2. **Nothing proves the audit-trail's write path and its own read path work
   together.** Every test in `audit_trail/tests.py` seeds `AuditLog` rows
   directly via `AuditLogFactory` and asserts against the `audit_trail`
   feature in isolation. None of them perform a real mutating action through
   another feature's router (an approval, a delegation, a check-in — each of
   which calls `record_audit_log` as a `BackgroundTasks` job per
   `security-architecture.md` §5) and then confirm that action is retrievable
   via `GET /audit-trail`. That gap is exactly what "check history tracking"
   means as a user-facing claim — the individual write and read tests each
   pass today, but nothing closes the loop between them.
3. **A fresh full-suite run right now establishes whether the tree is already
   green or already broken**, which the prior audits' own habit of quoting an
   actual `ddev exec uv run pytest -q` count (605→609 passed across two of
   them) makes the right first move rather than assuming green. This run:
   **645 passed, 0 failed** (`0:07:04`) — the tree is green going in, so this
   pass is purely additive coverage plus whatever the new assertions
   themselves surface, not a red-to-green recovery like the prior audit's.

## What Changes

- Establish one current, workflow-ordered test matrix covering every feature
  router (`auth`, `tenant`, `platform`, `org_structure`, `visitors`,
  `invitations`, `approvals`, `audit_trail`, `registrations`,
  `identity_verification`, `notifications`, `reports`, `sso`) plus the three
  cross-feature `tests/test_workflow_*.py` scenario files — folding forward
  what the prior audits already confirmed (API-01..API-19 plus SSO,
  push-notification dual-channel closure) and adding the two stages none of
  them had: **Delegation / relevantToMe** and **Audit Trail (history
  tracking)**.
- Extend the cross-feature workflow tests so at least one full run exercises,
  in the same scenario: a host delegating the step following their own,
  the delegate seeing the invitation via `relevantToMe`, the delegate acting
  on it, and every relevant push notification firing at each hop — mirroring
  the dual-channel-per-real-request bar the prior audit already set for
  email+push.
- Add an integration-style test (in `audit_trail/tests.py` or a workflow file,
  whichever keeps the assertion readable) that performs a real mutating
  action through its owning router, then confirms the resulting `AuditLog`
  row is retrievable — correct `action`, `entityType`, `entityId`, actor, and
  timestamp — through `GET /audit-trail` and `GET /audit-trail/{id}`, closing
  the write/read loop described above.
- Re-run and re-confirm the existing OTP/invitation email coverage (Mailpit
  real-delivery tests for OTP, approval, denial, reschedule) is still green
  and unaffected by the new code paths — not re-deriving it, since the prior
  audit already raised it to real-SMTP-round-trip evidence.
- Investigate, and either confirm-as-intended or flag as a follow-up (not fix
  silently), whether a delegate should receive a direct push notification at
  the moment they are delegated a step, versus relying solely on the
  broadcast-to-role-holders push already sent when the step first became
  current (`approvals/service.py::delegate_step` currently sends no
  notification of its own).
- Fix any concrete bug the full-suite run or the new integration coverage
  surfaces — scoped to what is actually found, not a refactor pass.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None planned. This is a verification and regression-closure pass: every
scenario it adds tests for is already part of each endpoint's or event's
existing, documented/intended contract (`openspec/specs/invitations/spec.md`,
`openspec/specs/approvals/spec.md`, `openspec/specs/audit-trail/spec.md`, and
`testing-standards.md` §2's mandatory permission-denied/tenant-isolation
cases). Fixing any bug found so behavior matches its own already-documented
contract is the same class of change the prior audits made without a
capability delta. If a gap turns out to require an actual contract change
(e.g., the delegate-push question above resolving to "yes, add a
notification"), that is out of scope here and gets flagged as a follow-up in
the closing summary instead of folded in silently. This change sets
`skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **Affected test files**: `tests/test_workflow_full_lifecycle.py`,
  `tests/test_workflow_staff_admin.py`, `tests/test_workflow_visitor.py`,
  `audit_trail/tests.py`, plus any other feature's `tests.py` the matrix
  review finds gapped.
- **Possible production-code fixes**: scoped to whatever concrete bug the
  full-suite run or the new integration coverage surfaces — none assumed in
  advance.
- **No schema/migration changes planned** beyond confirming the already-
  authored, untracked `alembic_tenant/versions/dfb1340caf66_audit_report_jobs.py`
  applies cleanly as part of the pass, the same way the prior audit confirmed
  the device-tokens migration.
- **No breaking changes.**
