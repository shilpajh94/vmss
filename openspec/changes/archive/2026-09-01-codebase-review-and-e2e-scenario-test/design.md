## Context

See `proposal.md` for the review that surfaced these findings and the
route/coverage gap analysis behind the new test. Relevant existing
patterns this design reuses rather than reinvents:

- `auth/service.py::sync_employee_directory` already wraps its whole batch
  in `try: ... except IntegrityError: rollback(); raise HTTPException(409,
  ...)` — the exact shape to copy for `assign_branch_role`/`create_role`/
  `update_role`.
- `org_structure/service.py::_commit_or_conflict` is the same pattern
  factored into a shared helper for that file's five entity types.
- `auth/repository.py::deactivate_employees_not_in` already does a single
  `update(...).where(...).returning(...).execution_options(synchronize_session=False)`
  bulk statement — the shape `approve_invitation`'s fix reuses, at
  single-row scope instead of bulk.
- `InvitationRepository` (`invitations/repository.py`) is a
  `TenantScopedRepository[Invitation]` — no existing method does a raw
  conditional `UPDATE`; one new repository method is needed.

## Goals / Non-Goals

**Goals:**
- Close all three verified bugs with the smallest change that matches an
  already-established pattern in the same file/module.
- Add one new end-to-end test that composes the specific route/interaction
  gaps identified in `proposal.md`'s route-inventory review — not a
  restatement of what the two existing workflow tests already cover.

**Non-Goals:**
- Not adding row-level locking (`SELECT ... FOR UPDATE`) anywhere — the
  atomic conditional `UPDATE` achieves the same correctness guarantee for
  this single-row transition without holding a lock across the request.
- Not fixing the pre-existing, narrower `has_active_org_chart_descendants`/
  `has_active_key_for_branch` TOCTOU window flagged during the diff
  self-review in the prior change — that one has a bounded blast radius
  (an orphaned org-structure row, not a security issue or duplicate
  external side-effect) and matches an existing, accepted limitation
  (`RoleRepository.has_active_grants` has the identical window). Flagged as
  a follow-up, not fixed here, to keep this change scoped to the three
  bugs that produce an actual user-visible bad outcome (a 500, or a
  duplicate email).
- Not wiring `identity_verification`'s OTP `proofToken` into the
  invitation/approval flow — confirmed as a pre-existing, documented open
  item (`security-architecture.md` §2's "fake-entry prevention"), not a
  regression this review should silently start closing.

## Decisions

**`IntegrityError` → 409 via `try`/`except` around the existing pre-check,
not a switch to a different concurrency-control mechanism.** Matches
`sync_employee_directory`'s existing shape exactly — same file, same
codebase convention, easiest to review and the most consistent outcome for
future readers of `auth/service.py`. Alternative considered: a
pre-emptive `SELECT ... FOR UPDATE` on the parent row before insert.
Rejected — heavier, introduces lock-ordering considerations this codebase
has never needed elsewhere, and the constraint-violation-catch approach is
already the local convention.

**Atomic conditional `UPDATE` for `approve_invitation`, not a
`SELECT ... FOR UPDATE`.** A new `InvitationRepository.approve_if_submitted
(invitation_id) -> Invitation | None` method issues
`UPDATE invitations SET status='approved', approved_at=now() WHERE id=:id
AND status='submitted' RETURNING *` (via SQLAlchemy Core `update(...)
.returning(...)`). Exactly one concurrent caller gets a non-`None` row back
(the one that performed the transition); every other caller gets `None` and
the service layer raises the same 409 the sequential
already-approved case already raises. The row lookup that already
happens in `router.py` (`service.get_invitation` — for 404/branch
resolution) stays as-is; only the actual status transition changes from
read-then-write to a single conditional write. Alternative considered:
locking the row (`SELECT ... FOR UPDATE`) at the top of `approve_invitation`
and holding it for the duration. Rejected — broader lock scope, and the
conditional-`UPDATE` gives the identical guarantee (exactly one winner)
without holding anything across the notification-dispatch call.

**Concurrency test simulates interleaving rather than firing real parallel
requests.** Two real concurrent HTTP requests against the test client would
be flaky (actual race timing, not deterministic). Instead: call the new
repository method (or the service function) twice in direct succession
within one test *without* re-fetching the invitation's status in between —
i.e. issue the same conditional `UPDATE` twice against the same starting
state, asserting the first call returns the transitioned row and the
second returns `None` (and would be turned into a 409 by the service). This
deterministically exercises the exact SQL-level race window the fix closes
without depending on real thread/task timing.

**The "fully packed" scenario test is one new file, not additions to the
two existing ones.** `test_workflow_staff_admin.py` and
`test_workflow_visitor.py` each have a narrow, named purpose (company-wide
admin setup; a single visitor's journey) — stretching either to also cover
two branches, role CRUD, and approval would make an already-long test
function harder to read and to debug on failure. A new
`test_workflow_full_lifecycle.py` composes the pieces neither existing file
does, named for what it actually is: the full-lifecycle, multi-branch,
multi-actor journey. It reuses `conftest.py`'s fixtures and the two
existing files' call/response-chaining style (each step's real response
feeds the next; no shortcut fixture skips a step a real client would have
to make).

**Scenario test outline** (see `proposal.md`'s "What Changes" for the full
narrative): platform login → tenant provision → admin login → `POST
/branches/provision` for Branch A (buildings/floors/departments/desks/gates
in one call) → build Branch B manually (`POST /branches`, one building) to
get a genuine two-branch tenant → `POST /auth/roles` (custom role) → `GET
/auth/permissions` → assign the custom role to a new staff user at Branch A
→ `DELETE .../branch-roles/{id}` (revoke it) → re-assign a standard role →
`POST /invitations` at Branch A → `POST /invitations/{id}/approve` (assert
`send_approval_notification.delay` called once, with the right
`invitation_id`, not stubbed to a no-op that swallows the assertion) →
`POST /registrations/walk-in` at Branch B (device key provisioned for
Branch B) → `GET /visit-info/departments`/`GET /visit-info/options`/`GET
/hosts/search` against Branch B feeding realistic values into the walk-in
payload → `GET /invitations?branchId=...` filtered per branch, confirming
each branch's own record only → `GET /reports/branches/rollup` reflecting
both branches → `DELETE /branches/{branchB.id}` while its device key/desk
are still active (409, from the prior change's guard) → deactivate/delete
those, then delete Branch B successfully (204).

## Risks / Trade-offs

- [Risk] The atomic-`UPDATE` fix changes `approve_invitation`'s internal
  data-access shape (no longer reads the ORM object and mutates it in
  place before commit). → Mitigation: the returned row from
  `RETURNING *` is re-hydrated as the same `Invitation` model instance
  shape the caller already expects (schema/response mapping unchanged);
  existing `test_approve_invitation_success`/`_already_approved_rejected`
  tests are re-run unmodified to confirm the observable contract is
  identical.
- [Risk] Catching `IntegrityError` broadly in `assign_branch_role`/
  `create_role`/`update_role` could mask an unrelated constraint violation
  as a misleading 409. → Mitigation: same accepted risk profile as the
  existing `sync_employee_directory`/`_commit_or_conflict` precedents,
  which this codebase already relies on — each catch site is narrowly
  scoped to the one `commit()` call immediately following the specific
  insert/update it's guarding, not a broad try block around unrelated work.

## Migration Plan

No data migration; pure code + test change. Deploy as a normal release —
the three fixes only change behavior for previously-500ing or
previously-duplicate-notifying requests, so there's no rollback concern
beyond a plain revert.
