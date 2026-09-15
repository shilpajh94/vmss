## 1. Fix the off-by-one rule lookup

- [x] 1.1 In `src/presentation/utils/approval-step-label.ts`'s `resolveNextStepPreviewLabel`, change `rules?.find((rule) => rule.stepOrder === 1)` to `rules?.find((rule) => rule.stepOrder === step.stepOrder + 2)`, with a comment explaining the 0-indexed/1-indexed mismatch between `CurrentApprovalStep.stepOrder` and `ApprovalWorkflowRule.stepOrder`.
- [x] 1.2 In `src/presentation/hooks/use-invitations-board.ts`'s `loadNextStepCandidates`, change `rules.find((rule) => rule.stepOrder === 1)` to `rules.find((rule) => rule.stepOrder === step.stepOrder + 2)`, with the same explanatory comment.

## 2. Verification

- [x] 2.1 Run typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`); confirm clean. *(All three pass clean.)*
- [x] 2.2 Manually re-verify against a real, correctly-configured multi-step workflow (e.g. "VIP Visitor": Reception → Host) that the "Pending:" preview now shows the next level's role, and the "Approve & Delegate" dropdown lists the correct employees — the exact case that surfaced this bug. **Unverified** — no backend access in this sandbox; needs your confirmation against the real "VIP Visitor" workflow.
