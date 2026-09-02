## Context

See `proposal.md` — Why for the three concrete findings motivating this pass
(no cross-feature workflow coverage of delegation/relevantToMe/audit-trail/
push, no write-then-read proof for the audit trail, and the fresh green
baseline).

This design extends, rather than re-derives, the workflow-ordered matrices
already built by the prior audits:
`openspec/changes/archive/2026-08-27-verify-api-regression-suite/`,
`openspec/changes/archive/2026-09-01-codebase-review-and-e2e-scenario-test/`
(route-vs-workflow coverage + `test_workflow_full_lifecycle.py`), and
`openspec/changes/archive/2026-09-01-verify-full-api-and-notification-delivery/`
(API-01..API-19 + SSO stage matrix, the email+push dual-channel closure,
Mailpit real-delivery tests). Current baseline as of this design
(`ddev exec uv run pytest -q`): **645 passed, 0 failed** in `0:07:04` — up
from the prior audit's 609, reflecting the newly-committed `audit_trail`
package and the delegation/`relevantToMe` feature.

Read directly (not assumed from names) before writing tasks from this design:
`src/vmss_api/audit_trail/{router,service,tasks,tests}.py` (17 tests, incl.
`test_tenant_schema_isolation`, the retry-exhaustion and redelivery-idempotent
report-generation tests), `src/vmss_api/approvals/service.py::delegate_step`
and its 13 tests in `approvals/tests.py` (`test_delegate_step_*`),
`src/vmss_api/invitations/router.py`'s `list_invitations` (`relevantToMe`
branch) and its 7 tests in `invitations/tests.py`
(`test_list_invitations_relevant_to_me_*`), and the three
`tests/test_workflow_*.py` files' existing stage structure (each is one long
scenario function with `# --- <stage> ---` comment dividers, not many small
test functions).

## Goals / Non-Goals

**Goals:**
- Prove, in at least one real end-to-end scenario, that delegation and
  `relevantToMe` work together across features the way a real user would hit
  them: host approves their own step → delegates the next step → delegate
  sees it via `relevantToMe` (and a non-delegate role-holder does not gain
  exclusive claim) → delegate acts on it → push notifications fire at the
  steps that already promise one.
- Close the write/read loop for audit trail: at least one test performs a
  real mutating action through its owning feature router and then confirms
  it is retrievable via `GET /audit-trail` (list) and `GET /audit-trail/{id}`
  (detail, including its diff), not just via `AuditLogFactory`-seeded rows.
- Re-confirm (not re-derive) the API-01..API-19 matrix, SSO, and the
  email+push dual-channel closure are all still green, and extend the matrix
  with the two stages the prior audits never had: Delegation/relevantToMe and
  Audit Trail.
- Resolve the delegate-push open question from proposal.md to a stated
  answer (confirmed-as-intended, or a flagged follow-up) — not silently
  dropped.
- End with a green full suite, clean `ruff`/`mypy` on `core/`, `auth/`, and
  `audit_trail/` (PII/audit-adjacent, per `project-rules.md`'s strict-typing
  scope), and a closing summary stating what was found.

**Non-Goals:**
- Not re-deriving the full API-01..API-19 stage-by-stage matrix or the
  email+push dual-channel matrix from scratch — the immediately-prior audit
  already did both in detail and left the suite at 609 passed. This pass
  spot-re-confirms those via the full run plus a named-regression-test check,
  the same "re-confirm without re-deriving" approach that audit itself used.
- Not adding a second real-SMTP-delivery (Mailpit) tier for the audit-report
  CSV/PDF export — report readiness is polled (`GET /reports/{job_id}`), not
  emailed (confirmed by reading `audit_trail/tasks.py` and `service.py`:
  neither calls an email/push sender), so there is no delivery channel here
  to raise to Mailpit evidence the way OTP/approval/denial/reschedule emails
  were.
- Not adding a "real" FCM delivery tier for push — unlike SMTP/Mailpit, there
  is no local capture equivalent for FCM; `notifications/tests.py`'s
  `_RecordingPushSender`/monkeypatch approach is already this repo's ceiling
  for push evidence, confirmed by reading its existing test file.
- Not archiving the prior verify/audit-trail/delegation changes this builds
  on — flagged in the closing summary as a follow-up action, since archiving
  is a separate workflow step from implementing this change's tasks.
- Not building a general cross-feature test helper/fixture for the new
  delegation+audit-trail scenario unless the workflow-file diff turns out to
  need one to stay readable — decide at apply time from the actual diff
  size, matching the immediately-prior audit's same non-goal.

## Decisions

**Decision 1 — Extend `test_workflow_full_lifecycle.py`'s existing single
scenario rather than adding a new workflow file.** The three
`test_workflow_*.py` files are each one long, linearly-narrated scenario
function with stage comments, not a suite of independent test functions —
adding a fourth file for "delegation + audit trail" would fragment the very
thing this pass is trying to prove (that these features compose within one
real journey, not in isolation). `test_full_lifecycle_workflow` already
creates an invitation with a role-identified approval chain and a host
(`# --- Staff-created invitation at Branch A, then manual approval ---`);
the delegation stage slots in immediately after the host's own step is
approved, before the chain's next role-identified step is approved directly.
*Alternative considered*: a new `tests/test_workflow_delegation_and_audit.py`
mirroring the other three's per-domain split (staff/admin, visitor,
lifecycle). Rejected — none of the three existing files are split by feature
package, they're split by *persona/journey* (full org lifecycle, staff/admin
setup, visitor-facing), and delegation+audit-trail's natural home is "things
that happen inside the invitation lifecycle," which is `test_workflow_full_lifecycle.py`'s
existing scenario, not a fourth persona.

**Decision 2 — The audit-trail write/read integration test lives in
`audit_trail/tests.py`, not the workflow files.** It needs one already-
authenticated actor performing one mutating call (simplest candidate:
`approvals/router.py`'s existing approve/deny/delegate endpoints, or
`invitations`' check-in — any of the `record_audit_log` call sites) followed
by a `GET /audit-trail` call asserting the resulting row's `action`,
`entityType`, `entityId`, actor, and timestamp, then a `GET
/audit-trail/{id}` call asserting the diff. This is a two-feature interaction
(the mutating feature's router + audit_trail's router), not a full multi-
stage journey, so it fits `audit_trail/tests.py`'s existing per-scenario test
function style better than inserting a detour into the long lifecycle
narrative. *Alternative considered*: add it as a stage in
`test_workflow_full_lifecycle.py` immediately after an existing mutating
call. Rejected as the primary location (a same-purpose assertion could still
be added there too, cheaply, once the delegation stage exists per Decision
1) — `audit_trail/tests.py` is the right owning location per
`fastapi-architecture.md`'s "tests colocate with the feature" convention,
and keeping the assertion self-contained there makes it easier to
extend/maintain as more mutating actions get added later.

**Decision 3 — The delegate-push question is answered by reading intent,
not by assuming.** `approvals/service.py::delegate_step` sends no
notification; `approve_step`'s `_activate_next_step` already sends a
broadcast push to whoever holds the step's `approver_role_id` at the branch
the moment the step first becomes current — and the delegate, by
construction (`_user_holds_role_at_branch` is checked before delegation
succeeds), is always a member of that broadcast set. So a role holder who is
later delegated the step has *already* received a push telling them a step
is awaiting approval; delegation only narrows *who* may act on it, it
doesn't newly inform anyone a step exists. Read `docs/features/notifications.md`'s
recipient-resolution table and `openspec/specs/approvals/spec.md`'s
delegation requirements directly to confirm whether "delegate specifically
notified" was ever an intended requirement before concluding either way in
the closing summary — do not guess from the code alone, since the code
proves current behavior but not intent.

## Risks / Trade-offs

- **[Risk]** Inserting a delegation stage mid-scenario into
  `test_full_lifecycle_workflow` could couple unrelated stages if the
  delegate needs a role/branch grant the scenario doesn't already set up. →
  **Mitigation**: reuse the scenario's existing second staff user / branch-
  role-grant machinery (`# --- Second staff user + branch-role grant ---` in
  `test_workflow_staff_admin.py` shows the established pattern in this
  codebase) rather than inventing a new user-provisioning path.
- **[Risk]** Adding push-notification assertions into a 655-line scenario
  function that doesn't already capture `.delay()` calls could require
  re-plumbing the whole function's task-patching setup. → **Mitigation**:
  follow the exact monkeypatch-`.delay`-before/restore-after pattern already
  used for `send_approval_notification`/`send_tracking_notification` in the
  same file (lines ~407-410, ~516-517) — add capture variables for the push
  task the same way, not a different mechanism.
- **[Risk]** The audit-trail write/read test could pass for the wrong reason
  if `record_audit_log`'s `BackgroundTasks` job hasn't actually run yet when
  the test asserts (a timing/ordering issue specific to `BackgroundTasks`
  execution in the test client). → **Mitigation**: check how the existing
  `audit_trail/tests.py` and other features' tests currently handle
  asserting on `BackgroundTasks`-dispatched work (likely already solved
  elsewhere in the codebase, e.g. `httpx.AsyncClient`'s lifecycle awaiting
  background tasks before the response returns) rather than adding a sleep
  or retry loop.

## Migration Plan

No schema changes proposed by this change itself. Confirm the already-
authored, untracked `alembic_tenant/versions/dfb1340caf66_audit_report_jobs.py`
applies cleanly against a fresh throwaway tenant schema (same method the
prior audit used for the device-tokens migration: apply the full tenant
chain, verify the resulting table's columns/indexes, drop the throwaway
schema) — this is a verification step, not a new migration to author.

## Open Questions

- Whether a delegate should receive a direct push at the moment of
  delegation is answered by Decision 3's investigation, not deferred — but
  if that investigation is inconclusive from the available docs/specs, state
  that plainly in the closing summary as a product question for the spec/
  design owner, rather than picking an answer un-grounded.
