## Context

`add-reception-approve-and-delegate` already added `loadNextStepCandidates(id)` to `use-invitations-board.ts`, which fetches `listApprovalWorkflowRulesUseCase.execute(invitation.visitorCategoryId)`, finds the `stepOrder === 1` rule, and resolves its `approverRoleId` to a name via `roleNameById` — but only on demand, when a single invitation's "Approve & Delegate" modal is opened. This change needs the same lookup, but for *every visible* Reception-step, multi-step card at once (to render "Pending:" on each), not just the one behind an open modal.

`visitorCategoryId` is a stable field on every invitation (`InvitationDetail`/`VisitRequestSummary`), and workflow rules are defined per category, not per invitation — so multiple cards sharing a category can share one fetch.

## Goals / Non-Goals

**Goals:**
- "Pending:" on a Reception-step, multi-step card shows the next step's role, computed once per distinct visitor category and reused across every card that shares it.
- Unify this with the existing `loadNextStepCandidates` lookup so there is one cache, not two independent fetches for the same data.

**Non-Goals:**
- No change to non-Reception steps or single-step workflows.
- No attempt at the "Assign & Approve" (no-workflow) feature raised in the same conversation — confirmed blocked on a missing backend capability; out of scope here.

## Decisions

**A `workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>` cache in `use-invitations-board.ts`, populated as invitation details load, not fetched per-card-render.**
Mirrors the existing "preload detail for requested invitations" effect (`pendingDetailFetchesRef`): a ref tracks which category ids have already been fetched (or are in flight) so the same category is never requested twice, even as many cards referencing it mount. Triggered whenever `invitationDetails` gains an entry whose `currentApprovalStep.stepOrder === 0`, `totalSteps > 1`, and `visitorCategoryId` isn't yet cached.
- *Alternative considered*: fetch on-demand per card via a `useEffect` inside `VisitRequestCard` itself. Rejected — pushes network concerns into a presentational component and reintroduces the N+1 problem this change exists to avoid; the board-level hook is already where every other shared lookup (`roleNameById`, `employeeNameById`) lives.

**`loadNextStepCandidates` (used by "Approve & Delegate") is refactored to read from this same cache instead of calling `listApprovalWorkflowRulesUseCase` itself.**
It becomes: read `workflowRulesByCategory[visitorCategoryId]` if present, else fetch and populate it (same fetch-and-cache helper the board-level effect uses), then filter `hostEmployees` as before. This removes a duplicate code path and guarantees the modal and the card preview never disagree about the next step's role.

**New `resolveNextStepPreviewLabel(detail, workflowRulesByCategory, roleNameById)` helper in `approval-step-label.ts`**, alongside the existing `resolveApproverLabel`.
`VisitRequestCard` calls this first; if it returns a label (Reception step, multi-step, category resolved), that's shown as "Pending:". Otherwise it falls back to the existing `resolveApproverLabel(detail.currentApprovalStep, ...)` unchanged — so every non-Reception or single-step case is provably untouched (same function, same call, as today).

## Risks / Trade-offs

- **A card can render before its category's rules have loaded** (brief window where "Pending:" would have nothing to show) → show the existing current-step label (Reception's own name) as a transient fallback until the cached rules arrive, then it swaps to the next-step preview — never a blank label.
- **A category with no `stepOrder === 1` rule, or an unresolvable role name** → falls back to the same current-step label; this is the same "nothing to show" case the "Approve & Delegate" empty-state dropdown already handles gracefully for the same underlying data gap.
