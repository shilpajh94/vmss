## Context

`useInvitationsBoard` (`src/presentation/hooks/use-invitations-board.ts`) already has everything this needs, just not composed together:
- `approve(id)` (lines ~275-309) already re-fetches the invitation detail after approving and exposes the *new* current step (`updatedDetail.currentApprovalStep`) — this is exactly the step that needs to be delegated.
- `delegate(id, delegateUserId)` (lines ~345-375) already reassigns a given current step to a specific employee, and already guards `stepOrder === 0` with an explicit error — the exact case this change replaces with a working path.
- `DelegateInvitationModal` filters `hostEmployees` by cross-referencing each employee's `branchRoles` against the step's `approverRoleId` (resolved to a name via `roleNameById`) — the same mechanism, applied to a *different* step's role, is enough for the new dropdown.
- `ListApprovalWorkflowRulesUseCase.execute(visitorCategoryId)` (used today only by `admin-workflows`) returns every step's `approverRoleId` for a visitor category, keyed by `stepOrder` — this is how the next step's role becomes knowable *before* approving, without a new backend endpoint. Both `InvitationDetail` and `VisitRequestSummary` already carry `visitorCategoryId` (nullable).

No backend change is implied anywhere in this design — it composes four already-existing use cases (`ApproveInvitationStepUseCase`, `GetInvitationDetailUseCase`, `ListApprovalWorkflowRulesUseCase`, `DelegateInvitationStepUseCase`) that today are never called in this sequence.

Note: `delegate()`'s `stepOrder === 0` guard ("Reception must approve this request before it can be delegated to another step") was added deliberately in the most recent commit on this branch (`806f4cc`), after `DelegateInvitationModal`'s unrelated "ownership step" unfiltered-picker exemption (from the still-in-progress `role-based-invitation-workflow` change) had already landed. It is a current, intentional rule, not a stale leftover — this design does not remove or route around it. This change never delegates stepOrder 0 itself; it approves stepOrder 0 (unchanged existing behavior) and then delegates the *resulting* stepOrder-1 step, which the guard already permits.

## Goals / Non-Goals

**Goals:**
- One user-facing action (button → dropdown → confirm) for Reception to approve their step and assign a specific person to the next step.
- No backend/API changes.
- Every step other than Reception's (stepOrder 0) is untouched.

**Non-Goals:**
- No change to what "Delegate" means or does for any non-Reception step (still: reassign the current step without approving).
- No general "pick anyone for any future step" feature — only Reception's own step, and only the very next step (stepOrder 1), gets this combined action.
- No optimistic UI / rollback of the approve call if the delegate call fails — see Risks.

## Decisions

**New `approveAndDelegate(id, delegateUserId)` in `use-invitations-board.ts`, not a new use case or backend endpoint.**
It sequences existing calls: `approveInvitationStepUseCase.execute(id, currentStep.id)` → `getInvitationDetailUseCase.execute(id)` (to get the new current step's id) → `delegateInvitationStepUseCase.execute(id, newCurrentStep.id, delegateUserId)` → one final `getInvitationDetailUseCase` + `loadDashboard()` refresh. Mirrors the existing `approve`/`delegate` functions' shape (loading-id state, try/catch, toast, board refresh) so it reads as "the same kind of thing" to a future maintainer.

**Fetching the next step's eligible employees requires one extra call the dashboard doesn't make today: `listApprovalWorkflowRulesUseCase.execute(invitation.visitorCategoryId)`.**
Triggered only when a Reception-step card with `totalSteps > 1` is expanded (same lazy-load pattern `loadDetail` already uses for step progress — no eager fetch for every card). Filter the returned rules for `stepOrder === 1`, resolve `approverRoleId` to a name via the already-loaded `roleNameById`, and filter `hostEmployees` the same way `DelegateInvitationModal` does today.
- *Alternative considered*: have the backend return the next step's role directly on `InvitationDetail`. Rejected — avoidable backend change; the data is already reachable from the frontend via an existing, already-wired use case.

**Reuse `DelegateInvitationModal`'s structure via a prop for "which step's role populates the dropdown," rather than a parallel modal component.**
The modal is already exactly "dropdown of eligible employees + confirm/cancel" — the only thing that needs to vary is which role filters the employee list and the confirm handler's label/copy ("Approve & Delegate" vs "Delegate"). A `mode: 'delegate' | 'approve-and-delegate'` prop (or equivalent) keeps one component instead of duplicating the eligibility-filtering logic.
- *Alternative considered*: a separate `ApproveAndDelegateModal` component. Rejected as needless duplication of the filtering logic for a modal that's otherwise identical.

**Partial-failure handling: if approve succeeds but delegate fails, do not attempt to undo the approval.**
There is no "unapprove" operation in this system, and fabricating one to paper over a transient failure would be riskier than surfacing the true state. Instead: catch the delegate call's failure separately from the approve call's, show an error naming the specific problem ("approved, but could not assign to X — please delegate manually"), and refresh the board so the card now shows its real state (advanced to the next step, unassigned or role-default-assigned) — the existing plain "Delegate" action on that now-current step (assuming it's not itself stepOrder 0 again) becomes the recovery path.

## Risks / Trade-offs

- **Two sequential network calls behind one click** → a failure between them leaves the request approved-and-advanced without the chosen assignment. Mitigated by the explicit two-part error message above; not eliminated, since there's no transactional "approve+assign" backend operation to fall back on.
- **Extra network round-trip on expanding a Reception-step, multi-step card** (the new `listApprovalWorkflowRulesUseCase` call) → acceptable; scoped to exactly the cards where this button can appear, same lazy-load-on-expand pattern already used for step detail.
- **`visitorCategoryId` is nullable** → if a Reception-step, multi-step invitation somehow has no visitor category, the next-step-role lookup has nothing to query. Treat this the same as the spec's "no eligible employees" case (empty-state dropdown, confirm disabled) rather than inventing a different error path — this should be rare in practice since a workflow is configured per visitor category.
