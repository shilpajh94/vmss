## Why

The API's per-endpoint contract tests are thorough, but the only two
chained, real-HTTP end-to-end tests that exist
(`tests/test_workflow_staff_admin.py`, `tests/test_workflow_visitor.py`)
each cover a narrow slice of a real journey: one branch only, no manual
invitation approval, no role CRUD, no bulk branch provisioning, no
walk-in-and-staff-invitation combined in one tenant, and neither asserts
that a notification was actually enqueued rather than silently no-op'd by
its own test stub. A fresh, skeptical code-review pass (four independent
angles: full route-vs-workflow-coverage inventory, business-logic
correctness re-check, and an adversarial self-review of the diff from the
just-shipped `harden-referential-integrity-and-rbac-gates` change) found
the codebase is largely solid, but surfaced three concrete, reproducible
response-contract bugs worth closing before adding more test surface on top
of them: two duplicate-insert races that surface as an unhandled 500
instead of the codebase's own established 409-on-conflict pattern, and one
check-then-act race that can dispatch a duplicate approval-email
notification under concurrent requests.

## What Changes

- **Fix: assigning an identical branch-role grant twice returns 409, not
  500.** `auth/service.py::assign_branch_role` inserts a new
  `UserBranchRole` with no duplicate pre-check or `IntegrityError` handling,
  even though the table has a `uq_user_branch_role` unique constraint on
  `(user_id, role_id, branch_id)` — a second identical assignment request
  (e.g. a client retry with no idempotency key, since this endpoint isn't
  one of `api-conventions.md` §3's listed idempotency-key endpoints) raises
  an unhandled `IntegrityError`, caught only by the generic global exception
  handler as a bare 500. Fixed by catching the constraint violation and
  translating it to 409, the same pattern `sync_employee_directory` already
  uses in the same file.
- **Fix: creating/renaming a role with a name that collides mid-race no
  longer 500s.** `auth/service.py::create_role`/`update_role` pre-check role
  name uniqueness via `get_by_name_case_insensitive` before insert, but
  don't catch the `IntegrityError` `Role.name`'s DB-level unique constraint
  raises if two requests race between the pre-check and the commit — same
  fix pattern as above, applied for defense-in-depth consistency (this is
  an unobservable-by-normal-testing race, not a deterministic bug like the
  branch-role one above; fixed anyway since the pattern and the fix are
  identical).
- **Fix: concurrent approval requests for the same invitation can dispatch
  two approval emails.** `invitations/service.py::approve_invitation` reads
  `invitation.status`, checks it's `submitted`, then mutates and commits —
  a classic check-then-act race with no row lock. Two near-simultaneous
  `POST /invitations/{id}/approve` requests can both pass the status check
  before either commits, both transition the row, and both enqueue
  `send_approval_notification.delay(...)`, sending the visitor two
  duplicate emails. Fixed with a single atomic conditional `UPDATE ...
  WHERE id = :id AND status = 'submitted' RETURNING ...` (same shape
  `auth/repository.py::deactivate_employees_not_in` already uses for a
  bulk update) so only one of the two racing requests actually performs the
  transition; the other observes 0 rows affected and is rejected with the
  same 409 the sequential "already approved" case already returns.
- **Add one new, deliberately "fully packed" end-to-end scenario test**
  (`tests/test_workflow_full_lifecycle.py`) chaining real HTTP calls (each
  step's real response feeding the next, never a shortcut fixture) through
  everything the two existing workflow tests don't compose together:
  platform tenant provisioning → admin login → **bulk branch provisioning**
  (`POST /branches/provision`) for a first branch, plus a second branch
  built to exercise a genuine two-branch tenant → **custom role creation**,
  **listing permissions**, assigning and **revoking** a branch-role grant →
  a staff-created invitation **followed by its manual approval**
  (`POST /invitations/{id}/approve`), asserting the approval notification
  was actually enqueued (call-count/kwargs asserted, not stubbed to a
  silent no-op) → a **walk-in registration against the second branch** in
  the same tenant → **`GET /invitations` listing/filtering** showing both
  the approved staff invitation and confirming the walk-in registration's
  own record is distinguishable from it → `visit_info` endpoints
  (host search, departments, options) feeding realistic values into the
  walk-in payload → the reports rollup reflecting both branches' activity →
  finally, exercising the branch-deletion guard from the prior change
  end-to-end (deleting the now-populated second branch is rejected with
  409 while its device key/org-chart are still active, then succeeds once
  they're cleaned up) — tying the previous change's fix into a realistic
  full journey instead of only isolated unit-style tests.
- No other production code changes are expected. If the new scenario test
  surfaces a further genuine integration bug, it's fixed the same
  "smallest correct change, decided at the time something is actually
  found" way the three fixes above were.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `auth`: adds a requirement that assigning a branch-role grant identical to
  one the user already holds is rejected with 409 (previously undefined —
  the request 500'd).
- `invitations`: extends the existing "A Submitted Invitation Can Be
  Manually Approved" requirement with a concurrency-safety scenario —
  concurrent approval requests for the same invitation SHALL result in
  exactly one transition and exactly one notification dispatch, consistent
  with the sequential "approving an already-approved invitation" behavior
  the requirement already documents.

## Impact

- **Code**: `src/vmss_api/auth/service.py` (`assign_branch_role`,
  `create_role`, `update_role` — `IntegrityError` → 409 translation),
  `src/vmss_api/invitations/service.py`/`repository.py`
  (`approve_invitation` — atomic conditional update).
- **Tests**: new `tests/test_workflow_full_lifecycle.py`; new unit-style
  regression tests for the three fixes above in `auth/tests.py` and
  `invitations/tests.py` (the concurrency case is tested by simulating two
  interleaved calls against the same row, not a real race — see
  `design.md`).
- **Compatibility**: all three fixes change a request that previously
  produced an unhandled 500 (or, for the invitations race, a double
  notification) into a clean, already-established 409 pattern. No
  currently-passing request's behavior changes — these are new, previously
  undefined error paths becoming defined ones, not a change to any
  documented success contract. The new scenario test adds coverage only;
  it doesn't touch any endpoint's contract.
