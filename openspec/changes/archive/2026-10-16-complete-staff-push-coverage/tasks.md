## 1. POC-push helper (design D1)

- [x] 1.1 In `invitations/service.py`, extract `_push_point_of_contact(tenant_db, tenant, invitation, *, push_builder, actor_user_id)` from the push half of `_notify_responsible_staff`. Skip a POC user who is the actor or the host. Run a role fan-out via `notify_role_at_branch` with `exclude_user_ids={actor, host}` and `reason="lifecycle_update"`. Do nothing when there's no POC or `branch_id` is `None`.
- [x] 1.2 Reduce `_ResponsibleStaff`/`_responsible_staff` to email recipients only, and make `_notify_responsible_staff` call `_push_point_of_contact` for its push.
- [x] 1.3 Run the existing deny/revert/reschedule POC tests (`test_revert_emails_host_and_poc_and_pushes_poc`, `test_deny_host_who_is_also_poc_gets_one_email_and_one_push`, `test_deny_with_role_poc_pushes_role_and_sends_no_email`) and confirm they pass unchanged. That's the no-regression check for 1.1 and 1.2.

## 2. Thread the actor through approve and extend (design D2)

- [x] 2.1 Add keyword-only `actor_user_id: uuid.UUID | None = None` to `approve_invitation` and `extend_invitation`.
- [x] 2.2 Pass `actor_user_id=user.id` from `invitations/router.py`'s approve and extend routes, and from `approvals/service.py::approve_step`'s final-step call.

## 3. Wire the five new events (spec "Approval, Check-In, Check-Out, Extension, and Edit Push the Point of Contact")

- [x] 3.1 `approve_invitation`: call `_push_point_of_contact(..., push_notifications.approved, actor_user_id=actor_user_id)` right after its `_notify_host`.
- [x] 3.2 `_perform_check_in` and `check_in_by_qr_token`: push `checked_in` to the POC after `_notify_host`. Use the actor from `_perform_check_in`, and `None` for QR. Confirm the idempotent no-change return path still sends nothing (design D4).
- [x] 3.3 `check_out_invitation` (actor `user_id`) and `check_out_by_qr_token` (actor `None`): push `checked_out` to the POC after `_notify_host`.
- [x] 3.4 `extend_invitation`: push `partial(push_notifications.extended, tz=tz)` to the POC after `_notify_host`.
- [x] 3.5 `edit_invitation`: push `edited` to the POC only when neither `poc_user_id` nor `poc_role_id` is in `changes`, with actor `user.id` (design D3). Leave the existing `poc_assigned` branch as is.

## 4. Tests (`invitations` tests, plus one in `approvals`)

- [x] 4.1 POC user pushed on staff check-in, and the host still gets its own push (monkeypatch `tasks.send_push.delay`, assert recipients and `action`).
- [x] 4.2 Role POC fan-out on QR check-out: every holder at the branch is pushed with `reason="lifecycle_update"`, and the host is excluded.
- [x] 4.3 POC pushed on direct approve, and on final-step approval via `approvals` `approve_step` (the latter in `approvals` tests).
- [x] 4.4 POC pushed on extend, with the new expiry in the payload. A rejected extend (422) sends no POC push.
- [x] 4.5 Edit without a POC change pushes the existing POC `edited`. An edit changing the POC from P to Q gives Q only `poc_assigned`, and P gets nothing.
- [x] 4.6 Exclusions: a POC who is the actor (staff check-out by the POC) gets no push, and a host who is also the POC gets exactly one push on check-in.
- [x] 4.7 No POC means the action succeeds with no POC push. A rejected check-in (410 expired window) sends no POC push.
- [x] 4.8 Permission-denied and tenant-isolation coverage (testing-standards §2): no new endpoint is added, so confirm the existing approve/extend/check-in/check-out permission-denied tests still pass. No new tenant-isolation test is needed because no new repository method is added.

## 5. Docs and verification

- [x] 5.1 Update `docs/features/invitations.md`'s notification section with an event × recipient table (host / POC / approver / visitor), matching proposal.md's gap table after this change.
- [x] 5.2 `ddev exec uv run ruff check`, `ruff format --check` and `mypy` on touched modules, then `ddev exec uv run pytest src/vmss_api/invitations src/vmss_api/approvals src/vmss_api/notifications`. Run it as a single process, never in parallel with another pytest run.