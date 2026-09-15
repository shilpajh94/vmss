## Context

Two independent `stepOrder` conventions coexist in this codebase, and nothing previously named the mismatch explicitly:
- `CurrentApprovalStep.stepOrder` (an invitation's active step): **0-indexed**. Reception is `stepOrder: 0`. Established by every `stepOrder === 0` check (`use-invitations-board.ts`'s delegate guard, `VisitRequestCard.tsx`'s `isReceptionStep`, the reception-dashboard guard) and by `displayStepLevel = stepOrder + 1`.
- `ApprovalWorkflowRule.stepOrder` (a workflow's configured levels): **1-indexed**. `SaveWorkflowUseCase.execute()` assigns `stepOrder = index + 1` for every level, on both create and update.

`resolveNextStepPreviewLabel` and `loadNextStepCandidates` (both added across `add-reception-approve-and-delegate` and `preview-next-approver-on-reception-step`) need to map from the first model to the second — "given the current invitation step (0-indexed), find the *next* step's config rule (1-indexed)" — and both hardcoded `rule.stepOrder === 1`, which is off by one in two ways at once: it doesn't advance to the next step at all, *and* it reads the 1-indexed rule set with a 0-indexed assumption.

## Goals / Non-Goals

**Goals:**
- Correct the mapping so both lookups find the actual next-level rule.

**Non-Goals:**
- No change to `SaveWorkflowUseCase`'s 1-indexed convention, or to `CurrentApprovalStep`'s 0-indexed convention — both are established, load-bearing conventions elsewhere; this fixes the code that bridges them, not either convention itself.

## Decisions

**Fix the lookup to `rule.stepOrder === step.stepOrder + 2`, not just `+ 1`.**
Deriving it explicitly (rather than re-hardcoding a different constant) makes the relationship self-documenting at the call site: current step's own rule is `step.stepOrder + 1` (0-indexed 0 → 1-indexed 1), so the *next* step's rule is one more than that, `step.stepOrder + 2`. A comment at both call sites spells this out so a future reader doesn't have to re-derive it from two other files.
- *Alternative considered*: normalize one of the two models (e.g., make `ApprovewWorkflowRule.stepOrder` 0-indexed everywhere). Rejected — far larger blast radius (touches `SaveWorkflowUseCase`, `WorkflowGroupList.tsx`'s displayed numbers, and every existing saved rule's stored value) for a fix that only needs to correct two lookup sites.

## Risks / Trade-offs

- **The two models' indexing conventions remain independently correct but mismatched by design** → accepted; it's how the backend/admin-form already models levels vs. steps, and this fix only teaches the two lookup sites that already need to bridge them how to do so correctly.
