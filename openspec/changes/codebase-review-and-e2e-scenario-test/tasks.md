## 1. Fix: Duplicate Branch-Role Grant Returns 409, Not 500

- [x] 1.1 In `auth/service.py::assign_branch_role`, wrap the
      `tenant_db.add(assignment); await tenant_db.commit()` step in a
      `try`/`except IntegrityError`, mirroring
      `sync_employee_directory`'s existing pattern: on
      `IntegrityError`, `await tenant_db.rollback()` and raise
      `HTTPException(409, detail="User already holds this role at this
      branch")`.
- [x] 1.2 Add a regression test to `auth/tests.py`: assign the same role to
      the same user at the same branch twice via `POST
      /auth/users/{id}/branch-roles`; assert the first succeeds (201) and
      the second returns 409, with the original grant still intact
      (`GET /branches/current` or a direct repository check still shows
      exactly one assignment).

## 2. Fix: Role-Name Uniqueness Race Returns 409, Not 500

- [x] 2.1 In `auth/service.py::create_role` and `update_role`, wrap the
      insert/rename + commit in the same `try`/`except IntegrityError` ->
      409 pattern as task 1.1, guarding the existing
      `get_by_name_case_insensitive` pre-check against the race window
      between that check and the commit.
- [x] 2.2 No new test required for the race itself (it's not
      deterministically reproducible without simulated concurrency) —
      confirm the existing `test_create_role_duplicate_name_rejected`-style
      tests (pre-check path) still pass unchanged.

## 3. Fix: Concurrent Invitation Approval No Longer Double-Dispatches

- [x] 3.1 Add `InvitationRepository.approve_if_submitted(invitation_id) ->
      Invitation | None` (`invitations/repository.py`): a single
      `update(Invitation).where(Invitation.id == invitation_id,
      Invitation.status == "submitted").values(status="approved",
      approved_at=<now>).returning(Invitation)` — returns the updated row
      if this call performed the transition, `None` if the invitation
      wasn't `submitted` (already approved, or approved by a racing call
      that won).
- [x] 3.2 Update `invitations/service.py::approve_invitation` to call
      `approve_if_submitted` instead of reading `invitation.status`,
      mutating in place, and committing; raise the existing 409
      ("Invitation is not awaiting approval") when it returns `None`, and
      dispatch the approval notification only when it returns a row.
- [x] 3.3 Add a deterministic regression test to `invitations/tests.py`:
      call `approve_if_submitted` (or `approve_invitation`) twice in direct
      succession against the same `submitted` invitation without
      re-fetching between calls; assert the first call transitions the row
      and the second returns `None`/409, and that exactly one
      `send_approval_notification.delay` call was recorded.
- [x] 3.4 Re-run the existing `test_approve_invitation_success`,
      `test_approve_invitation_already_approved_rejected`, and (from the
      prior change) `test_approve_invitation_soft_deleted_branch_succeeds`
      to confirm the atomic-update rewrite preserves their exact observable
      behavior.

## 4. Fully Packed End-to-End Lifecycle Scenario Test

- [x] 4.1 Create `tests/test_workflow_full_lifecycle.py` following the
      chaining style of the two existing workflow test files (each step
      uses the previous step's real HTTP response — token, id, tracking
      id — never a shortcut fixture for something a real client would have
      had to call an endpoint to get).
- [x] 4.2 Platform login → tenant provisioning → admin login (mirrors
      `test_workflow_staff_admin.py`'s opening steps).
- [x] 4.3 `POST /branches/provision` to bootstrap Branch A's full org chart
      (building/floor/department/reception-desk/security-gate) in one call
      — the bulk-provisioning path no existing test exercises.
- [x] 4.4 Build Branch B manually (`POST /branches` + one building) so the
      tenant genuinely has two branches for the rest of the flow to
      exercise branch-scoping across.
- [x] 4.5 `POST /auth/roles` (custom role) → `GET /auth/permissions` →
      assign the custom role to a new staff user at Branch A
      (`POST /auth/users/{id}/branch-roles`) → revoke it
      (`DELETE .../branch-roles/{assignment_id}`) → assign a standard role
      instead, so the rest of the flow has a real branch-scoped staff user.
- [x] 4.6 `POST /invitations` at Branch A (staff-created) → `POST
      /invitations/{id}/approve` — assert the response transitions to
      `approved` AND assert `send_approval_notification.delay` was called
      exactly once with this invitation's id (patch/record the call rather
      than stubbing it to a bare no-op the way the existing visitor
      workflow test does).
- [x] 4.7 Provision a device key for Branch B, then `GET
      /visit-info/departments`, `GET /visit-info/options`, and `GET
      /hosts/search` against Branch B, feeding a real returned department/
      purpose/duration/host into a `POST /registrations/walk-in` payload
      for Branch B.
- [x] 4.8 `GET /invitations?branchId=<A>` and `?branchId=<B>` — confirm each
      branch's listing shows only its own record and the approved status
      from step 4.6 is reflected.
- [x] 4.9 `GET /reports/branches/rollup` — confirm both branches' activity
      is reflected.
- [x] 4.10 Attempt `DELETE /branches/{branchB.id}` while its device key and
      building are still active — assert 409 (the prior change's guard).
      Deactivate the device key and delete the building, then delete
      Branch B again — assert 204.
- [x] 4.11 If any step in this chain surfaces a genuine integration bug
      beyond the three already fixed in Sections 1-3, fix it with the
      smallest correct change and note what was found in this task's
      notes at apply time — same "decide the fix when something is
      actually found" posture as prior audit-style changes in this repo.

## 5. Verification

- [x] 5.1 Run `ddev exec uv run pytest` for the full suite; confirm 100%
      green including every new test from Sections 1-4.
- [x] 5.2 Run `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` on the full tree.
- [x] 5.3 Run `ddev exec uv run mypy` on `core/`, `auth/`, and any other
      touched module in strict scope per `project-rules.md`'s static-typing
      rule.
- [x] 5.4 Confirm no existing test's assertions changed meaning — only the
      three specific behaviors in Sections 1-3 changed (500/duplicate-email
      → clean 409), and Section 4 is additive test coverage only.
