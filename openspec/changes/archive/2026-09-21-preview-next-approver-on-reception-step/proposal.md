## Why

On a card whose current approval step is Reception's own (stepOrder 0) in a multi-step workflow, the "Pending:" label currently shows "Reception" — the step Reception is already looking at. That's redundant to the person viewing their own queue; what's actually useful is a preview of where the request goes *next* (e.g. the Host level), which today only becomes visible after opening "Approve & Delegate".

## What Changes

- On a card whose current approval step is stepOrder 0 (Reception) and whose workflow has more than one total step, the "Pending:" label (both the collapsed badge and the expanded-card detail line) SHALL show the *next* step's (stepOrder 1) approver role instead of the current step's.
- Every other card (non-Reception step, or a single-step Reception-only workflow) is unaffected — "Pending:" continues to show the current step's approver, exactly as today.
- Internally, the workflow-rule lookup this needs is cached per visitor category (not re-fetched per invitation), and the existing "Approve & Delegate" modal's own next-step lookup is unified with this same cache instead of fetching separately.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: The "Pending:" label on a Reception-step, multi-step card previews the next step's approver instead of naming Reception's own step.

## Impact

- **Affected code**:
  - `src/presentation/hooks/use-invitations-board.ts` — new cache (`workflowRulesByCategory`, keyed by `visitorCategoryId`) populated once per distinct category as Reception-step, multi-step invitation details load; `loadNextStepCandidates` (from the prior `add-reception-approve-and-delegate` change) reuses this same cache instead of fetching independently.
  - `src/presentation/utils/approval-step-label.ts` — new helper resolving the next-step preview label from the cached rules + `roleNameById`.
  - `src/presentation/components/invitation-board/VisitRequestCard.tsx` — the "Pending:" text (collapsed badge and expanded line) uses the preview label when the card is at a Reception, multi-step step; otherwise unchanged.
  - `src/presentation/components/invitation-board/KanbanColumn.tsx`, `staff-dashboard.tsx`, `admin-invitations.tsx` — thread the new cache through, same pattern as `roleNameById`/`employeeNameById` today.
- **Not affected**: the backend API surface (no new/changed endpoints — reuses `ListApprovalWorkflowRulesUseCase`, already wired for this exact purpose by the prior change), and the "Assign & Approve" idea for no-workflow invitations raised in the same conversation — that one is on hold, since it requires a backend capability (setting a host on an invitation with no approval step) that does not exist today; this change does not attempt it.
