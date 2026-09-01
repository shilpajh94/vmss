## Why

Hosts and approval delegates currently have no way to find "their" invitations
through the API — `GET /invitations` only supports branch-scoped admin
filtering (`invitations:view` on a branch), so a host with no view permission
on a branch cannot see an invitation they registered a visitor against, and
there is no way for a host to hand off their workflow's next approval step to
a specific person instead of leaving it open to anyone holding that role. The
frontend team needs both to build a personal "relevant to me" inbox view.

## What Changes

- Add a `relevantToMe` filter to `GET /invitations` that returns invitations
  where the caller is either the snapshotted host (`step_order=0` row's
  `approver_user_id` in `InvitationApprovalStep`) or has been delegated the
  step immediately following the host's step. This filter bypasses the
  branch-scoped `invitations:view` permission check — it is a personal
  worklist, not a branch-admin view.
- Add `POST /invitations/{invitationId}/approval-steps/{stepId}/delegate` so a
  host, once their own `step_order=0` step is approved, can delegate the
  next role-identified step (`step_order=1`) to a specific person instead of
  leaving it open to anyone holding that step's role. Only the step
  immediately following the host's own step is delegable — later
  role-identified steps in a 3+ level workflow are not.
- The delegate must hold the target step's configured role at the
  invitation's branch (or company-wide) — the same matching rule already used
  to authorize a role-identified step action (`_user_holds_role_at_branch`).
- Once delegated, the delegate (not just any holder of the role) is the only
  caller who can approve/reject that step, alongside the existing
  `invitations:approve-override` bypass. The delegate sees the invitation in
  their own `relevantToMe` list.
- Delegation is recorded for audit (who delegated, to whom, when), consistent
  with the project's mutating-action audit trail requirement.
- No change to how the last step finalizes the invitation — delegation only
  changes *who* may act on a step, not the strict step-order/finalization
  flow already in place.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `approvals`: adds step delegation (a role-identified step can be assigned
  to a specific delegate by the host, once the host's own step is approved)
  and extends step-action authorization to check for a delegate before
  falling back to the role-membership check.
- `invitations`: adds the `relevantToMe` list filter to `GET /invitations`,
  including its distinct (non-branch-scoped) authorization rule.

## Impact

- **Code**: `src/vmss_api/approvals/models.py` (new delegation columns on
  `InvitationApprovalStep`), `src/vmss_api/approvals/service.py` (delegate
  action, authorization check), `src/vmss_api/approvals/repository.py`
  (delegate write, relevant-to-me step lookup), `src/vmss_api/approvals/router.py`
  (new delegate endpoint), `src/vmss_api/approvals/schemas.py` (delegate
  request/response schemas), `src/vmss_api/invitations/router.py` and
  `service.py`/`repository.py` (new `relevantToMe` query param and query
  path).
- **Database**: a new Alembic migration under `alembic_tenant/` adding
  `delegated_to_user_id`, `delegated_by_user_id`, `delegated_at` columns to
  `invitation_approval_steps` (nullable, FKs to `users.id`).
- **API**: one new endpoint, one new query parameter on an existing endpoint.
  Additive only — no existing field/response shape changes, so this ships
  into `/api/v1` directly per `api-conventions.md` §2.
- **Tests**: new cases in `approvals/tests.py` (delegate success, delegate by
  non-host rejected, delegate to a user lacking the role rejected, delegate
  before host's own step is approved rejected, delegate of a step other than
  step_order=1 rejected, delegated step actioned only by delegate,
  override-permission still bypasses) and `invitations/tests.py`
  (`relevantToMe` returns host's invitations, returns delegate's invitations,
  does not require `invitations:view`, tenant-isolation case).
