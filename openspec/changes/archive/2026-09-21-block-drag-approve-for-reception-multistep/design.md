## Context

`VisitRequestCard.tsx` already computes `isReceptionStep` and `canApproveAndDelegate` (from `add-reception-approve-and-delegate`) — `isReceptionStep && (detail?.currentApprovalStep?.totalSteps ?? 0) > 1` is exactly the condition this change needs to also gate on. `isDraggable` is passed down from `KanbanColumn`/the page based on column status (`status === 'requested'`); the card already narrows it further with `isDraggable && !isApproving` for its own `draggable` attribute and cursor styling.

## Goals / Non-Goals

**Goals:**
- A Reception-step, multi-step card cannot be dragged to Approved at all.
- Every other card's drag-and-drop behavior is byte-for-byte unchanged.

**Non-Goals:**
- No change to `KanbanColumn`'s drop handling, or to `approve()`/`approveAndDelegate()` themselves — this is purely about which cards can initiate a drag.

## Decisions

**Disable the HTML5 `draggable` attribute itself for the affected cards, rather than allowing the drag and rejecting it at drop-time.**
`VisitRequestCard.tsx`'s existing `draggable={isDraggable && !isApproving}` becomes `draggable={isDraggable && !isApproving && !isLockedToApproveAndDelegate}`, reusing the same boolean that already gates the "Approve & Delegate" button — so "shows the button" and "cannot be drag-approved" can never drift out of sync (both read the same expression). The grab-cursor styling (`cursor-grab active:cursor-grabbing`) is gated the same way, so the card doesn't visually invite a drag it won't accept.
- *Alternative considered*: keep the card draggable, and have `KanbanColumn`'s drop handler (or `approve()`) check the step and reject with an error toast. Rejected — lets the user complete a drag gesture that then silently fails or shows an error, which is a worse experience than the card simply not lifting in the first place, for no benefit (there's no case where allowing-then-rejecting is more correct than not-draggable).

## Risks / Trade-offs

- **A user might not immediately understand *why* a specific card won't drag** (no explicit disabled-state affordance beyond the missing grab cursor) → accepted as minor; the "Approve & Delegate" button is still visible and is the obvious next action on that same card.
