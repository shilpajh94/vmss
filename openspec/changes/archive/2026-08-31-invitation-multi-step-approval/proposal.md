## Why

The admin UI can already configure per-visitor-category approval chains
(`ApprovalWorkflowRule`, API-05/06 — CRUD only, live today), but no invitation
ever evaluates them: invitations aren't tagged with a visitor category, and
`POST /invitations/{id}/approve` is still a single flat `submitted → approved`
step open to anyone holding `invitations:approve`. Configured workflows are
invisible to the runtime, so a tenant that sets up a 3-step chain in the admin
UI sees no different behavior at check-in time. This change makes the
configured rules actually govern approval.

## What Changes

- Add `visitorCategoryId` (required) to `InvitationCreate`, and to
  `InvitationOut`/`InvitationListItemOut`. **BREAKING**: existing clients of
  `POST /invitations` must start sending `visitorCategoryId`; the column is
  nullable at the DB level (pre-existing rows have none) but the request
  schema requires it going forward.
- On invitation submission, snapshot the matching category's active,
  ordered `ApprovalWorkflowRule` rows into new `InvitationApprovalStep` rows
  (one invitation → many steps), so a later edit to the workflow config never
  retroactively changes an invitation already in flight. A category with zero
  active rules gets no steps — that invitation keeps today's single-approve
  behavior unchanged.
- New endpoints:
  - `POST /invitations/{id}/approval-steps/{step_id}/approve` — approves one
    step; on the last step, flips the invitation to `approved` and fires the
    existing QR/notification logic; otherwise unlocks the next step.
  - `POST /invitations/{id}/approval-steps/{step_id}/reject` — rejects one
    step and moves the invitation straight to its existing terminal `denied`
    state (same state/fields the current single-approve deny path already
    uses). Rejection is terminal: no resubmission endpoint in this change: a
    denied invitation is done, same as today.
- Extend the invitation detail read (and the unauthenticated tracking lookup)
  with the current pending step's `stepOrder`/`approverRoleId` (and total step
  count) so the UI can render "waiting on: Manager, step 2 of 3" instead of a
  single Approve button. Additive fields only, no existing field changes.
- Tighten authorization: approving/rejecting a step requires the caller to
  hold `invitations:approve` **and** hold (via `UserBranchRole`) the role
  matching that step's `approverRoleId` at the invitation's branch, OR hold a
  new override permission (`invitations:approve-override`, granted to `admin`
  only) that bypasses the role-match check. The existing blanket
  `POST /invitations/{id}/approve` keeps working unchanged, but only for
  invitations with zero snapshotted steps (unconfigured category) — calling it
  on a workflow-backed invitation now returns 409, since that invitation must
  go through its steps.
- `escalatesAt`/`autoApprovesAt` are computed and stored on each step
  (from the rule's `escalationMinutes`/`autoApproveMinutes`) but nothing in
  this change acts on them yet — no scheduled auto-approve or escalation
  notification job. That's follow-up scope once the fields exist for the UI
  to render countdowns against.

## Capabilities

### New Capabilities
- `approvals`: runtime evaluation of `ApprovalWorkflowRule` against a
  submitted invitation — the `InvitationApprovalStep` snapshot, step
  sequencing/approve/reject transitions, and role-matched authorization for
  acting on a step. (The existing `visitors` capability stays config-CRUD
  only, matching its current documented scope; this is the "not-yet-built
  approvals feature" its own model docstring already anticipates.)

### Modified Capabilities
- `invitations`: `visitorCategoryId` on create/response schemas, invitation
  detail/tracking responses expose current-step info, the blanket
  `POST /invitations/{id}/approve` is restricted to invitations with no
  workflow steps (409 otherwise), and rejection via a step routes to the
  existing denial terminal state.

## Impact

- **Code**: new `src/vmss_api/approvals/` feature package (`models.py`,
  `repository.py`, `service.py`, `router.py`, `schemas.py`, `tests.py`) per
  `fastapi-architecture.md` §1, registered in `api.py`/`main.py`
  (`api-documentation.md` §2). Changes to `invitations/models.py` (new
  `visitor_category_id` column + Alembic tenant migration),
  `invitations/schemas.py`, `invitations/service.py` (category→rule lookup at
  submission, step-snapshot call, restrict blanket approve), and
  `invitations/router.py` (wire new endpoints, extend detail/tracking
  response).
- **Data**: new `invitation_approval_steps` table (tenant schema); new
  `alembic_tenant/` migration for it plus the `invitations.visitor_category_id`
  column, applied to every existing tenant schema per
  `database-architecture.md` §5.
- **Auth**: new permission code `invitations:approve-override` in
  `auth/rbac_catalog.py`, granted to `admin` by default.
- **Clients**: React portal and Flutter app must send `visitorCategoryId` on
  invitation creation and switch their approve UI to the per-step endpoint
  for workflow-backed invitations — flagged as a breaking change for those
  two separate-repo clients per `api-conventions.md` §2.
- **Docs**: `docs/features/invitations.md` and `docs/features/visitors.md`
  both need updates (the latter's "not yet built" note about runtime
  evaluation becomes stale); new `docs/features/approvals.md`.
