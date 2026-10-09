## Why

Today, when a visit request's approval workflow has more than one step, Reception (the step-0 approver) can only approve their own step — approving simply advances the request to whichever employee the workflow's role-based default assigns to step 1. Delegating (picking a specific person) is a separate action, and it is explicitly blocked on the Reception step ("Reception must approve this request before it can be delegated to another step"), so Reception has no way to hand the request to a *specific* person for the next step in the same motion as approving. Reception wants to do both in one action: approve their own step and choose exactly who takes the next one.

## What Changes

- On a Reception-step (stepOrder 0) card whose workflow has more than one step, replace the current inert/blocked "Delegate" action with a single "Approve & Delegate" button.
- Activating it opens a dropdown of employees eligible for the *next* step's role (stepOrder 1) — not the current step's role. Selecting a person and confirming approves Reception's own step and assigns that specific person as the approver of the resulting next step, in one user-facing action.
- On a Reception-step card whose workflow has only one step (Reception is the only approver), nothing changes — the card offers only the existing plain approve (drag-to-Approved); there is no one to delegate to.
- Every other approval step in every workflow keeps today's separate Approve (drag-to-column) and Delegate (button + dropdown, reassigns the *current* step without approving) actions, unchanged.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: Adds the Reception-step "Approve & Delegate" combined action (dropdown scoped to the next step's role, approve-then-assign semantics) and removes the non-functional plain "Delegate" affordance from Reception-step cards.

## Impact

- **Affected code**:
  - `src/presentation/hooks/use-invitations-board.ts` — new `approveAndDelegate(invitationId, delegateUserId)` orchestration: approve the current (Reception) step via the existing `ApproveInvitationStepUseCase`, then re-fetch the invitation detail to get the new current step's id, then call the existing `DelegateInvitationStepUseCase` for it. No new use cases or API endpoints — this sequences two calls that already exist.
  - Fetching the *next* step's required role before approval: call the existing `ListApprovalWorkflowRulesUseCase` (already used by `admin-workflows`, not currently wired into the dashboard) with the invitation's `visitorCategoryId`, filter for `stepOrder === 1`, and resolve its `approverRoleId` the same way `DelegateInvitationModal` already resolves the current step's role to eligible employees.
  - `src/presentation/components/invitation-board/DelegateInvitationModal.tsx` (or a new sibling component) — the dropdown's eligible-employee list is computed from the *next* step's role instead of the current step's role, only for this Reception-step flow.
  - `src/presentation/components/invitation-board/VisitRequestCard.tsx` — on a Reception-step (stepOrder 0) card, show "Approve & Delegate" instead of "Delegate" when `totalSteps > 1`, and show neither when `totalSteps === 1`.
  - `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` / `use-staff-dashboard.ts` — wire the new combined handler through, alongside the existing `approve`/`delegate`.
- **Not affected**: the backend API surface (no new or changed endpoints), every non-Reception approval step's Approve/Delegate behavior, and single-step (Reception-only) workflows.
- **Risk flagged in design.md, not blocking**: the combined action is two sequential API calls behind one UI confirmation — if the second call (assigning the next step) fails after the first (approving) already succeeded, the request is left approved-and-advanced but not assigned to the chosen person. This needs an explicit error-handling decision, covered in design.md.
