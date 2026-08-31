## Why

The staff dashboard's step-aware approval UI is already wired against the shipped
API, but two gaps block it from working end to end: the client has no way to
obtain the `stepId` that `POST /invitations/{id}/approval-steps/{stepId}/approve|
reject` requires, and there is no way to route the first approval to the
invitation's selected host — every approval step is role-based today, even for
categories where the intent is "the host approves first."

## What Changes

- Add `id` to `CurrentApprovalStepOut` (embedded as `currentApprovalStep` in
  `InvitationOut`, `InvitationDetailOut`, and `InvitationTrackingOut`), sourced
  from the already-loaded `InvitationApprovalStep.id` — no new endpoint needed.
- Surface the invitation's resolved host as `hostId` on `InvitationOut` and
  `InvitationDetailOut` output (the underlying `host_id` column and submission-time
  resolution from `hostId`/`hostNameOrEmail` already exist; they are just not
  surfaced or used for approval routing today).
- **BREAKING** (approval-step shape, additive-compatible on the wire): when an
  invitation's resolved host (`host_id`) is not null, submission now always
  snapshots an implicit host-approval step as `stepOrder` 0, ahead of the
  category's configured `ApprovalWorkflowRule` chain (if any). This changes the
  step sequence for any category that has both a resolvable host and configured
  workflow rules, and changes zero-rule categories from "no steps, blanket
  single-approve" to "one step, host-approves" whenever the host resolves.
- Add a nullable `approver_user_id` column to `InvitationApprovalStep` (making
  `approver_role_id` nullable too) so a step can name a specific approving user
  instead of a role — exactly one of the two is set per row.
- Extend step-action authorization: a step with `approver_user_id` set requires
  the caller to be that exact user (or hold `invitations:approve-override`),
  instead of the existing role-match check.

## Capabilities

### New Capabilities

(none — both changes extend existing capabilities' requirements)

### Modified Capabilities

- `approvals`: adds a host-identified step kind (`approver_user_id`) alongside
  the existing role-identified kind, a new "step 0 = host approval, always
  first when the host resolves" snapshot rule, and the corresponding
  authorization branch. Also adds `id` to the step shape returned to callers.
- `invitations`: surfaces `hostId` on `InvitationOut`/`InvitationDetailOut` output
  schemas (input-side resolution from `hostId`/`hostNameOrEmail` is unchanged).

## Impact

- **Code**: `src/vmss_api/approvals/schemas.py` (`CurrentApprovalStepOut`),
  `src/vmss_api/approvals/models.py` (`InvitationApprovalStep`),
  `src/vmss_api/approvals/service.py` (`_authorize_step_action`),
  `src/vmss_api/invitations/schemas.py` (`InvitationOut`, `InvitationDetailOut`),
  `src/vmss_api/invitations/service.py` (`_build_approval_steps`,
  `get_current_approval_step`).
- **Database**: one `alembic_tenant` migration adding `approver_user_id`
  (nullable FK to `users`) to `invitation_approval_steps` and relaxing
  `approver_role_id` to nullable, applied to every tenant schema per
  `database-architecture.md` §5.
- **API contract**: `currentApprovalStep.id` and `InvitationOut.hostId` are new,
  additive response fields — existing clients ignoring unknown fields are
  unaffected. The step-sequence behavior change (host as step 0) is a business-
  rule change, not a wire-format break, but changes what step sequence a client
  observes for affected categories.
- **Frontend**: unblocks the already-built staff-dashboard approve/reject UI
  (uses `currentApprovalStep.id` as the `stepId` path param) with no client
  changes required beyond consuming the new fields.
