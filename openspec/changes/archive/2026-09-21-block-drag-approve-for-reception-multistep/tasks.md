## 1. Block drag-and-drop for Reception + multi-step cards

- [x] 1.1 In `src/presentation/components/invitation-board/VisitRequestCard.tsx`, add `const isLockedToApproveAndDelegate = isReceptionStep && (detail?.currentApprovalStep?.totalSteps ?? 0) > 1` (independent of `onApproveAndDelegateClick` being passed, so it holds even if that prop is ever absent). *(`canApproveAndDelegate` now derives from it: `Boolean(onApproveAndDelegateClick) && isLockedToApproveAndDelegate`.)*
- [x] 1.2 Change the card's `draggable` attribute from `isDraggable && !isApproving` to `isDraggable && !isApproving && !isLockedToApproveAndDelegate`.
- [x] 1.3 Update the cursor-styling className (`isDraggable && !isApproving ? 'cursor-grab active:cursor-grabbing' : ''`) to also require `!isLockedToApproveAndDelegate`, so the card doesn't show a grab cursor it won't honor.

## 2. Verification

- [x] 2.1 Run typecheck (`tsc -b`), lint (`oxlint`), and build (`npm run build`); confirm clean. *(All three pass clean.)*
- [x] 2.2 Confirm at the code level: a Reception-step card with `totalSteps > 1` has `draggable={false}` and no grab cursor, regardless of `isDraggable`/`isApproving`. *(`isLockedToApproveAndDelegate` is `true` in that case, and both `draggable` and the cursor className AND against `!isLockedToApproveAndDelegate`.)*
- [x] 2.3 Confirm at the code level: a Reception-step card with `totalSteps === 1`, and every non-Reception-step card, keeps its existing `draggable`/cursor behavior exactly as before — `isLockedToApproveAndDelegate` is `false` for both. *(For `totalSteps === 1`, `totalSteps > 1` is false; for a non-Reception step, `isReceptionStep` is false — either way `isLockedToApproveAndDelegate` is `false`, leaving `draggable`/cursor exactly as the original `isDraggable && !isApproving` expression.)*
- [x] 2.4 No backend access in this sandbox — flag as unverified whether the actual drag-and-drop interaction (not just the `draggable` attribute value) behaves as expected in a real browser, consistent with prior changes in this session. **Unverified.**
