## Why

"Approve & Delegate" exists so Reception approves their own step and assigns a specific person to the next step in one action. But a Reception-step card in a multi-step workflow can still be dragged straight to the "Approved" column — a plain approve that advances the request without assigning anyone, bypassing the whole point of the new action. The two paths shouldn't coexist for the same card.

## What Changes

- A card whose current approval step is Reception's (stepOrder 0) in a workflow with more than one total step can no longer be dragged to the "Approved" column — "Approve & Delegate" becomes the only way to advance it.
- Every other card (non-Reception step, or a single-step Reception-only workflow) is unaffected — drag-and-drop approval keeps working exactly as today.

## Capabilities

### Modified Capabilities
- `staff-dashboard`: Drag-and-drop approval is disabled specifically for a Reception-step, multi-step card; "Approve & Delegate" is the only path for it.

## Impact

- **Affected code**:
  - `src/presentation/components/invitation-board/VisitRequestCard.tsx` — the card becomes non-`draggable` when its current approval step is stepOrder 0 and `totalSteps > 1`, reusing the same condition already computed for showing the "Approve & Delegate" button.
- **Not affected**: the backend API surface, `KanbanColumn`'s drop handling (unchanged — it only ever receives an id for a card that was actually draggable), and every other card's drag/approve behavior.
