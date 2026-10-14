## Why

Approval is a one-way door today. `approve_if_submitted` only moves
`submitted → approved`, and no endpoint moves an invitation back. When a
reviewer approves the wrong request (wrong card, wrong visitor, approved
before a background check came back), staff have no way to undo it. The
visitor keeps a valid QR pass until it expires. Reception teams have asked
for an explicit, audited "revert approval" action. They also asked that
every invitation action in the portal be confirmed before it is sent, so a
mis-click cannot approve, deny or revert anything in the first place.

## What Changes

- Add `PATCH /api/v1/invitations/{id}/revert-approval` with a mandatory
  `reason` (1–500 chars). It moves an `approved` invitation back to
  `submitted`, but only if the visitor has never checked in
  (`checkInStatus = unused`). Any other state returns 409, and the
  transition is atomic (a conditional `UPDATE`, like approve and deny).
- Revert clears `approvedAt` and records `approvalRevertedAt`,
  `approvalRevertedByUserId` and `approvalRevertReason`. The fields are
  overwritten on each revert, and every revert is also audit-logged as
  `invitation_approval_reverted`. All three fields are new, additive
  fields on the invitation output.
- For a workflow-backed invitation, every snapshotted
  `InvitationApprovalStep` resets to `pending`. This clears the step's
  actor, timestamp and delegation, and recomputes the step-1 clock.
  Approval restarts from step 1 and step 1's approver(s) receive the usual
  "awaiting approval" push. An invitation with no steps simply returns to
  `submitted` and can be approved again with `POST /invitations/{id}/approve`.
- While reverted, the visitor's existing QR pass stops admitting them,
  because every check-in path already requires an approved status. The QR
  row is kept, so re-approval re-sends the same pass. No new token is
  issued.
- Notify the primary contact by email (new
  `send_approval_revert_notification` Celery task) that their approval was
  withdrawn and their pass is on hold until it is reviewed again. Notify
  the host by push (new `push_notifications.approval_reverted`).
- Add a new RBAC permission, `invitations:revert-approval`. It is granted
  by default to the standard `admin`, `reception` and `host` roles. A
  tenant migration backfills it to those standard roles in existing
  tenants (idempotent; custom roles are untouched).
- Companion web change (VMMS_WEB `openspec/changes/add-invitation-approval-revert`):
  - Add a "Revert approval" action on Approved cards that have not been
    checked in, with a reason dialog.
  - Route every state-changing invitation action on both boards through a
    confirmation step: approve, approve-step, approve & delegate, delegate,
    deny/reject-step, revert approval, check-out, reschedule and edit.
    This also closes the gap where the Staff Dashboard approves with no
    confirmation at all.

No **BREAKING** change: one new endpoint, new nullable columns, new output
fields and one new permission code. No existing endpoint's contract or
status meaning changes. `submitted` keeps its meaning ("awaiting a
decision").

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `invitations`: new requirements for reverting an approved,
  not-yet-checked-in invitation back to `submitted` (reason, atomicity,
  notifications including the host push, audit) and for its QR pass being
  on hold until re-approval.
- `approvals`: new requirement that an approval revert resets every
  snapshotted step to `pending` and restarts the workflow from step 1.
  Also clarifies that "rejection is terminal" is unaffected, because only
  approved invitations can be reverted.
- `auth`: new requirement that `invitations:revert-approval` exists in the
  catalog, is granted by default to `admin`, `reception` and `host`, and is
  backfilled to existing tenants' standard roles.

## Impact

- **Code (API)**:
  - `invitations/`: `router.py` (new route), `service.py`
    (`revert_invitation_approval`), `repository.py`
    (`revert_approval_if_eligible`), `models.py` (3 new columns),
    `schemas.py` (request schema plus 3 new output fields),
    `push_notifications.py`, `tasks.py` (new email task plus template),
    and `tests.py`.
  - `approvals/`: `repository.py` (`reset_all_for_invitation`) and
    `repository.py` (`activate_current_pending`, shared with
    `approve_step`), with the step-approver push reused.
  - `auth/rbac_catalog.py`.
- **Migrations**: two `alembic_tenant` revisions. One adds the 3 invitation
  columns; the other backfills the permission grant to the standard roles. No
  global-schema migration is needed beyond the catalog row, which is
  inserted idempotently the same way `bff38dfa42e7` does it.
- **Docs**: `docs/features/invitations.md` (new endpoint, permission and
  revert semantics).
- **Clients**: VMMS_WEB (companion change; see above). Flutter is
  unaffected until it chooses to surface the action. The new output
  fields are additive.
- **Ops**: run `alembic -c alembic_tenant.ini heads` before the PR, since
  tenant migrations are being added.
