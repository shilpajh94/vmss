## Context

See `proposal.md` - Why for motivation. Relevant current state (from
reading the code, not restated in the proposal):

- `Invitation` (`invitations/models.py`) has a plain `status: String(20)`
  (no DB enum), no category reference, and existing atomic
  conditional-`UPDATE...WHERE status=X...RETURNING` methods in
  `InvitationRepository` (e.g. `approve_if_submitted`) that
  `invitations/service.py::approve_invitation`/`deny_invitation` already
  call, each enqueuing a Celery task afterward (`tasks.send_approval_notification`,
  `tasks.send_denial_notification`) — this is the exact mutation and
  notification path a workflow's *final* step approval, and *any* step's
  rejection, need to trigger. `deny_invitation`/`POST /invitations/{id}/deny`
  already exist (`add-invitation-lifecycle-actions`, merged) with a mandatory
  `denial_reason` and `denied_at` — this change reuses that path rather than
  inventing a second denial mechanism.
- `ApprovalWorkflowRule` (config, live) currently lives in
  `visitors/models.py`, not a dedicated package. Its own docstring already
  earmarks "evaluating these rules against an actual visit request" as the
  job of a not-yet-built `approvals` feature, and `project-rules.md`'s
  directory listing independently reserves `approvals/` for exactly this
  ("configurable approval workflow engine"). This change builds that
  package; it does not move `ApprovalWorkflowRule` itself, which stays
  config-CRUD in `visitors/`.
- A user's role is not global: `UserBranchRole` ties `(user_id, role_id,
  branch_id)`, with `branch_id = NULL` meaning company-wide. Role-matching a
  step's `approverRoleId` must check this table at the invitation's branch
  (row with that `branch_id`, or a company-wide row), not a single
  `user.role` field — there isn't one.

## Goals / Non-Goals

**Goals:**
- Wire the already-live `ApprovalWorkflowRule` config into an actual
  per-invitation approval sequence, reusing the existing approve/deny
  mutation and notification code paths rather than duplicating them.
- Keep the change additive to backward compatibility wherever the spec
  doesn't say otherwise: an invitation with no snapshotted steps behaves
  exactly as it does today.

**Non-Goals (explicitly deferred, confirmed with the product owner):**
- No scheduled job acts on `escalatesAt`/`autoApprovesAt` in this change —
  they're computed and stored for the UI to render, nothing more (see
  `specs/approvals/spec.md`'s "Escalation and Auto-Approve Timestamps"
  requirement). A follow-up change adds the Celery beat enforcement.
- No resubmission flow for a rejected invitation. Rejection is terminal,
  reusing the existing single-shot `deny` semantics.
- No change to `ApprovalWorkflowRule` CRUD itself (`visitors/` package) —
  this change only reads active rules at snapshot time.

## Decisions

### 1. New `approvals/` package; steps snapshotted at invitation-creation time by `invitations/service.py`, not by `approvals`
`InvitationApprovalStep`'s model, repository, the step approve/reject
service logic, and the new step router live in a new
`src/vmss_api/approvals/` package per `fastapi-architecture.md` §1 — this is
exactly the package `project-rules.md`'s directory structure already
reserves for "the configurable approval workflow engine."

The *snapshot* itself, however, is created inline inside
`invitations/service.py::create_invitation`, in the same transaction as the
`Invitation` insert — not via a call out to `approvals/service.py`. Reason:
snapshot-then-commit must be atomic (a submitted invitation must never exist
without its steps, or vice versa), and the cleanest way to guarantee that
without a cross-feature transaction hand-off is for `invitations/service.py`
to import `visitors.repository.ApprovalWorkflowRuleRepository` (to read
active rules for the category — a dependency `invitations` already needs
for category validation) and `approvals.models.InvitationApprovalStep` (the
model only, not `approvals.service`), build the step rows, and
`session.add()` them alongside the `Invitation` before the single commit.

This keeps the dependency graph one-directional and acyclic:
`invitations` → `visitors` (already true) and `invitations` →
`approvals.models` (new, model-only). `approvals.service` is free to import
`invitations.service`'s `approve_invitation`/`deny_invitation` (for
finalization — decision 2) without creating a cycle, since
`invitations.service` never imports `approvals.service`.

**Alternative considered**: have `approvals.service` own snapshot creation,
called from `invitations.service` after the invitation insert, same
transaction, passing the open session. Rejected only because it would need
`invitations.service` → `approvals.service` (for the call) alongside
`approvals.service` → `invitations.service` (for finalization, decision 2),
a cycle resolvable only with local/deferred imports — avoidable entirely by
keeping snapshot construction as data-shaping logic co-located with the
other "what does creation produce" logic in `invitations.service`.

### 2. Step finalization reuses `invitations.service.approve_invitation`/`deny_invitation` verbatim
When the last step is approved, `approvals.service.approve_step` calls
`invitations.service.approve_invitation` for the actual
`submitted→approved` mutation and QR/notification dispatch — the same
atomic conditional `UPDATE...WHERE status='submitted'` already guards
against a race with, e.g., the blanket approve endpoint. When any step is
rejected, `approvals.service.reject_step` calls
`invitations.service.deny_invitation` the same way. `approvals.service`
does not reimplement either mutation. This is why `approve_invitation`'s
precondition stays `WHERE status='submitted'` unchanged (`specs/invitations
/spec.md` doesn't touch that requirement's wording) — the invitation's own
status doesn't change until the workflow finishes, so the guard is still
correct when called from a workflow context.

### 3. Blanket approve endpoint gains a "has steps?" guard, not a new status
`POST /invitations/{id}/approve` gains one additional check in
`invitations.service.approve_invitation`: before running the existing
conditional update, query whether any `InvitationApprovalStep` row exists
for this invitation id; if so, raise the same conflict exception the
already-approved case raises (409), without touching status. This is a
single `EXISTS` query, not a join, and only runs on this one endpoint's
call path — no cost added to the common (no-workflow) case beyond one
indexed existence check.

### 4. Role-match authorization lives in `approvals.service`, not a `Depends()` chain
Unlike `require_permission`/`authorize_branch_id`, "does the caller's
assigned role match *this specific step's* `approverRoleId`" needs the step
row loaded first (which role is even being checked depends on which step is
current) — a dependency factory can't parameterize on data fetched inside
the handler. So `approve_step`/`reject_step` in `approvals/router.py` keep
the existing `Depends(require_permission("invitations:approve"))` +
`authorize_branch_id_tolerant` dependencies (branch access, as today), then
`approvals.service.approve_step(session, user, invitation_id, step_id, ...)`
itself loads the current step and checks: does `user` have a
`UserBranchRole` row with `role_id == step.approver_role_id` and
(`branch_id == invitation.branch_id` or `branch_id IS NULL`)? If not, does
`user.has_permission("invitations:approve-override")`? If neither, the
service raises the same forbidden-style exception
`org_structure/deps.py`'s branch-authorization helpers already raise for a
403, which the router lets propagate to the global exception handler /
`error_response` path unchanged.

### 5. `InvitationApprovalStep.status` is a plain string, not a DB enum
Matches `Invitation.status`'s existing convention (plain `String(20)`, no
Postgres enum type) rather than introducing the first native enum column in
this table family. Validated at the Pydantic layer via a Python `Enum` in
`approvals/schemas.py`.

### 6. New permission `invitations:approve-override`
Named to match the existing hyphenated-action convention already in
`auth/rbac_catalog.py` (`invitations:watchlist-override`), not a three-part
`invitations:approve:override` colon form used nowhere else in the catalog.
Granted to `admin` only in the seed catalog (`ROLE_PERMISSIONS["admin"]`
already implies every code, so this needs no special-casing there) — no
other role gains it by default.

### 7. Current-step exposure is a nested optional object, computed per lookup
`InvitationOut`/tracking response gain `currentApprovalStep:
{stepOrder, approverRoleId, totalSteps} | None`, populated by one extra
indexed query (`WHERE invitation_id=... AND status='pending' ORDER BY
step_order LIMIT 1`, plus a `COUNT(*)`) run only on the single-invitation
detail/tracking path — never on `GET /invitations` list rows, so this adds
no N+1 risk under `query-performance.md` §2 (a list endpoint already never
touches per-row child rows here; this is unchanged).

## Risks / Trade-offs

- **[Risk]** `visitorCategoryId` becoming required on `POST /invitations`
  breaks any client that doesn't send it, immediately on deploy — flagged
  **BREAKING** in the proposal. → **Mitigation**: DB column stays nullable
  (existing rows keep no category), so this is purely a request-validation
  change, not a data backfill; coordinate the deploy with the React/Flutter
  teams per `api-conventions.md` §2's client-notice expectation.
- **[Risk]** A step's `approverRoleId` may reference a `Role` nobody at the
  invitation's branch actually holds (e.g. the role was assigned company-
  wide to someone since reassigned, or never assigned at that branch),
  stalling the workflow with no one able to approve except an
  `invitations:approve-override` holder. → **Mitigation**: this is a data-
  hygiene problem for the admin UI (already out of this API's scope per the
  proposal), but the override permission exists precisely as the escape
  hatch; not treated as a bug in this change.
- **[Risk]** Computing `escalatesAt`/`autoApprovesAt` per-step (decision in
  the approvals spec) rather than all at submission time means a UI that
  only reads the invitation once at submission won't see step 2's deadline
  until it re-fetches after step 1 is approved. → **Mitigation**: this is
  exactly the same re-fetch the UI already needs to see `currentApprovalStep`
  advance from step 1 to step 2, so no additional UI complexity beyond what
  decision 7 already required.

## Migration Plan

1. `alembic_tenant/` revision: add nullable `invitations.visitor_category_id`
   (FK `visitor_categories.id`) and create `invitation_approval_steps`
   (FK `invitation_id → invitations.id`, `approver_role_id → roles.id`,
   unique-among-not-soft-deleted `(invitation_id, step_order)`, per
   `database-architecture.md` §5's tenant-migration process). Apply to every
   existing tenant schema the same way any tenant migration is rolled out
   (today: the one tenant in `tenants`).
2. Add `invitations:approve-override` to `PERMISSION_CODES` and grant it to
   `admin`'s permission set — a data migration/seed update, not a schema
   migration, following however the existing permission catalog is synced
   into `role_permissions` today.
3. Ship code and migrations together; no phased rollout needed since the
   only behavior change for *existing* invitations (no category, no steps)
   is the new required field on create, and that's enforced only going
   forward — nothing about already-submitted invitations changes shape.
4. Rollback: revert the code deploy and downgrade the two migrations; no
   destructive step (steps are additive tables/columns), so this is a
   standard Alembic downgrade with no manual data cleanup.

## Open Questions

- Should any role besides `admin` be seeded with
  `invitations:approve-override` by default (e.g. a `security` or reception
  supervisor role)? Deferred to the tenant's own RBAC configuration via the
  existing role/permission management endpoints — doesn't change this
  change's specs, approach, or tasks either way.
