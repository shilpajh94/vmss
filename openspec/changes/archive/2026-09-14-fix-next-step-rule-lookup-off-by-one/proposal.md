## Why

Verifying `preview-next-approver-on-reception-step` against a real, correctly-configured workflow ("VIP Visitor": Reception → Host) showed the "Pending:" preview still stuck on "reception" instead of "host", and the "Approve & Delegate" dropdown (from `add-reception-approve-and-delegate`) still empty/wrong — even after a hard refresh and with the workflow properly configured (confirmed via the Admin → Workflows screen).

Tracing it down: `SaveWorkflowUseCase.execute()` (`src/data/use-cases/save-workflow.ts`) saves each `ApprovalWorkflowRule.stepOrder` as `index + 1` — **1-indexed** (Level 1 → `stepOrder: 1`, Level 2 → `stepOrder: 2`). But an invitation's `CurrentApprovalStep.stepOrder` is **0-indexed** (Reception's own step is `stepOrder: 0`, confirmed by every `stepOrder === 0` check elsewhere in the codebase, and by `displayStepLevel = stepOrder + 1`). Both `resolveNextStepPreviewLabel` and `loadNextStepCandidates` looked up the next step's config rule with `rule.stepOrder === 1` — which, in the 1-indexed config data, is actually *Reception's own rule*, not the next step's. The lookup was silently finding the wrong rule (or matching nothing useful) instead of erroring, so this went undetected until tested against real, complete data.

This is a pre-existing defect in both features (`add-reception-approve-and-delegate`, already archived, and `preview-next-approver-on-reception-step`, implemented but not yet archived) — no new behavior is being specified here; both changes already specified "preview/populate from the next step's role," and this restores that already-specified behavior. Per project convention (see `fix-visitor-category-badgecolor-nullable`), this change sets `skip_specs: true` rather than inventing a requirement delta for a straightforward defect fix.

## What Changes

- Both lookups now search for the config rule at `currentApprovalStep.stepOrder + 2` (accounting for the 1-index/0-index mismatch between the two models) instead of the hardcoded `1`.
- No behavior is newly specified; this makes the already-specified "next step" preview/dropdown actually resolve to the correct step for any invitation whose current step is stepOrder 0.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — `skip_specs: true`; no requirement text changes, only a defect fix to already-specified behavior)

## Impact

- **Affected code**:
  - `src/presentation/utils/approval-step-label.ts` — `resolveNextStepPreviewLabel`'s rule lookup.
  - `src/presentation/hooks/use-invitations-board.ts` — `loadNextStepCandidates`'s rule lookup.
- **Not affected**: `SaveWorkflowUseCase`'s 1-indexed `stepOrder` convention itself (unchanged — this is a real, load-bearing convention other code, like `WorkflowGroupList.tsx`'s displayed level numbers, already depends on), the backend API surface, and every other consumer of `ApprovalWorkflowRule`.
