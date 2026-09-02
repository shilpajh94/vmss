## 1. Restore Non-Admin Role Push, Keep Admin Excluded

- [x] 1.1 `notifications/service.py::notify_step_approver` — in the
      role-identified branch, resolve the `Role` via
      `RoleRepository(tenant_db).get(approver_role_id)`; if it resolves and
      `role.name.lower() == "admin"`, return without dispatching (no log —
      this is expected, intended behavior, same posture as the prior
      change's "no warning log" decision). Otherwise (including an
      unresolvable role — fail open, see design.md), call
      `notify_role_at_branch` exactly as it did before
      `restrict-invitation-push-to-hosts-only`.
- [x] 1.2 Import `RoleRepository` from `vmss_api.auth.repository` in
      `notifications/service.py`.

## 2. Update Tests

- [x] 2.1 `approvals/tests.py::test_approve_step_non_final_role_identified_step_sends_no_push`
      — rename/rework: build the two-step invitation's second role
      specifically named `admin` (case-sensitive seed name) and assert no
      push; add a sibling test using a non-`admin`-named role (e.g.
      `reception`, matching the existing `_two_step_invitation` helper's
      default role names unless overridden) asserting `notify_role_at_branch`
      *is* called with that role's id and the invitation's branch.
- [x] 2.2 `invitations/tests.py::test_create_invitation_role_identified_step_sends_no_push`
      — same split: an Admin-named role-identified first step asserts no
      push; a non-Admin role-identified first step asserts
      `notify_role_at_branch` fires with the configured role/branch.
- [x] 2.3 `notifications/tests.py` (or `approvals/tests.py`/
      `invitations/tests.py`, whichever already has DB-role fixtures handy)
      — add a case for `notify_step_approver` itself: role resolves to
      `admin` → no dispatch; role resolves to a non-admin name → dispatch;
      role id doesn't resolve to any row → dispatch (fail-open case from
      design.md).

## 3. Documentation

- [x] 3.1 `docs/features/notifications.md` — correct the "Recipient
      resolution" table and its role-dispatch note back to: role-identified
      steps push to every role holder, except the tenant's standard `admin`
      role, which never receives push.

## 4. Verification

- [x] 4.1 `ruff check`/`ruff format --check` clean on touched files.
- [x] 4.2 `mypy src/vmss_api` clean.
- [x] 4.3 Full `pytest` suite green.
