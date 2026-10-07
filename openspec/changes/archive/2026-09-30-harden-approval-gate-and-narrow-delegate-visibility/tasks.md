## 1. Repository: narrow clause (c), add clause (e)

- [x] 1.1 In `src/vmss_api/invitations/repository.py`, add a required
      `default_host_role_id: uuid.UUID` parameter to `_relevant_to_me_filter`.
- [x] 1.2 Add `current_step.delegated_to_user_id.is_(None)` to the
      `current_role_holder` `exists()` subquery's `where()` clause (Decision 3).
- [x] 1.3 Add the new `default_host_role_holder` `exists()` subquery against
      `UserBranchRole` (role_id = `default_host_role_id`, user_id = caller,
      branch_id matches the invitation's branch or is company-wide/NULL) and
      OR it into the filter's top-level `or_(...)` (Decision 2).
- [x] 1.4 Update `_relevant_to_me_filter`'s docstring to describe the new
      clause (e) and the narrowed clause (c), replacing the stale reference
      to `invitation-relevant-to-me-retains-role-visibility-after-delegation`.
- [x] 1.5 Thread `default_host_role_id` through `InvitationRepository.list_page`
      (accept it as a parameter, pass to `_relevant_to_me_filter` only when
      `relevant_to_user_id` is set).

## 2. Service and router: resolve the role once per request

- [x] 2.1 In `src/vmss_api/invitations/service.py::list_invitations_page`,
      accept `default_host_role_id: uuid.UUID | None = None` and pass it to
      `InvitationRepository.list_page`.
- [x] 2.2 In `src/vmss_api/invitations/router.py`'s `relevantToMe` handler,
      when `relevant_to_me` is true, resolve
      `org_structure.service.get_default_host_role(tenant_db)` and pass its
      `.id` into `list_invitations_page` (Decision 1) — skip the resolution
      entirely on the branch-scoped (non-`relevantToMe`) path.

## 3. Invitations tests: rewrite for the new clause behavior

- [x] 3.1 Update/rename
      `test_list_invitations_relevant_to_me_role_holder_keeps_visibility_once_...`
      (or equivalent) so it now asserts a non-default-host-role holder LOSES
      visibility once their role's current step is delegated to someone else.
      (Renamed to `test_list_invitations_relevant_to_me_role_holder_loses_visibility_once_delegated`.)
- [x] 3.2 Add a test: a default-host-role holder who never delegated, was
      never delegated, and never acted keeps seeing the invitation via
      `relevantToMe=true` after its `stepOrder` 0 step is delegated to a
      specific host.
- [x] 3.3 Add a test: the same default-host-role holder still sees the
      invitation after it is fully `approved` or `denied`.
      (Covered for `approved`; `denied` is symmetric via the same clause
      (e) query, which has no status predicate at all.)
- [x] 3.4 Add a test: a holder of a later, non-default step's role
      (`stepOrder` 1+) sees the invitation while that step is current and
      undelegated, and loses visibility once it's delegated to someone else
      who is not them. (Covered by the existing
      `..._role_holder_sees_current_step_invitation` test plus the rewritten
      3.1 test.)
- [x] 3.5 Confirm existing tests for clauses (a), (b), (d), the
      `X-Branch-ID`-ignored scenario, and the empty/no-match scenario still
      pass unmodified (they don't depend on clause (c)/(e)). Verified none
      of their test users are granted the "reception" role.
- [x] 3.6 Run the tenant-isolation and permission-denied checks
      (`testing-standards.md` §2) still pass for `GET /invitations` with
      `relevantToMe=true`. (Updated the two direct-repository isolation
      tests to pass `default_host_role_id`.)

## 4. Approvals tests: regression coverage for the ordering guarantee

- [x] 4.1 Add a test: delegating `stepOrder` 0 to a host (step remains
      `pending`), then the resolved host attempts to delegate `stepOrder` 1
      → 409, no delegation recorded, `hostId` unchanged.
      (`test_delegate_ownership_step_alone_does_not_unlock_next_step_for_delegation`)
- [x] 4.2 Add a test: same setup, but the caller instead holds
      `invitations:approve-override` → still 409 on the `stepOrder` 1
      delegate attempt.
      (`test_delegate_step_override_permission_cannot_skip_pending_earlier_step`)
- [x] 4.3 Add a test: same setup, but the caller instead holds `stepOrder`
      1's `approverRoleId` role directly → still 409 (role match alone
      doesn't bypass the ordering check).
      (`test_delegate_step_role_holder_cannot_skip_pending_earlier_step`)
- [x] 4.4 Add a test: the same override/role-holding callers succeed in
      delegating `stepOrder` 1 once `stepOrder` 0 is actually approved
      (positive control, confirms the 409s above are about ordering, not
      unrelated authorization failures).
      (`test_delegate_step_role_and_override_succeed_once_earlier_step_approved`)
- [x] 4.5 Add the mirrored pair of tests for `approve_step`/`reject_step`
      directly on a not-yet-current step (already partially covered by
      existing "Acting on a step out of order is rejected" tests — extend
      only if a resolved-host or override-permission variant is missing).
      Added `test_approve_step_override_permission_cannot_skip_pending_earlier_step`;
      the plain role-match case was already covered by
      `test_approve_step_out_of_order_rejected`, and the resolved-host
      variant was already covered by
      `test_delegate_step_before_host_step_approved_rejected`'s approve-path
      equivalent being structurally identical (`_require_is_current` is
      shared code, not a separate check per authorization clause).

## 5. Specs and docs

- [x] 5.1 Confirm `openspec/specs/invitations/spec.md` and
      `openspec/specs/approvals/spec.md` will be updated by
      `openspec archive` from this change's delta specs — no manual edit
      needed ahead of archiving.
- [x] 5.2 Update `docs/features/invitations.md` to note the narrowed
      `relevantToMe` behavior for non-default-host roles and the new
      permanent default-host-role clause, per `api-conventions.md` §2
      (existing-endpoint behavior change).

## 6. Verification

- [x] 6.1 `ddev exec uv run pytest src/vmss_api/invitations/tests.py
      src/vmss_api/approvals/tests.py` green. (310 passed.)
- [x] 6.2 `ruff check` / `ruff format --check` clean on touched files.
- [x] 6.3 `mypy` clean on `src/vmss_api/invitations` and
      `src/vmss_api/approvals` (PII/auth-adjacent scope per
      `project-rules.md`). The only 2 errors reported
      (`router.py`'s pre-existing `date | None`/`time | None` `.isoformat()`
      union-attr warnings) are unrelated to this change — confirmed
      identical (same errors, one line earlier) on the unmodified file via
      `git stash`.
- [x] 6.4 Full `ddev exec uv run pytest` suite green before requesting
      review. 863 passed. One pre-existing failure,
      `tests/test_workflow_full_lifecycle.py::test_full_lifecycle_workflow`
      (`assert 4 == 3` on a push-notification count around a later-step
      delegation), reproduces identically with this change's files stashed
      out — confirmed unrelated to this change, not touched by it.
