## 1. Data layer

- [x] 1.1 Add `approvalRevertedAt`, `approvalRevertedByUserId` and `approvalRevertReason` (all `.nullish()`) to the invitation detail zod schema. The board's summary schema is fed by the API list item, which doesn't carry them.
- [x] 1.2 Add a `revertApproval` endpoint (`/invitations/:id/revert-approval`) to `data/api/api-endpoints.ts`.
- [x] 1.3 Add `revertApproval(id, reason)` to the `VisitRequestSummaryRepository` interface and to `infrastructure/visit-request-summary-repository.ts` (`PATCH`, body `{ reason }`).
- [x] 1.4 Add `RevertInvitationApprovalUseCase` in `data/use-cases/` and register it in `composition-root.ts`.

## 2. Shared confirmation UI

- [x] 2.1 Extend `ui/ConfirmDialog.tsx` with `tone` (defaulting to `danger`), `isBusy`, `busyLabel` and `children`. Confirm that the existing CRUD-page usages render unchanged.
- [x] 2.2 Rebase `ApproveInvitationModal` on `ConfirmDialog` (tone `success`), naming the visitor and REQ ID.
- [x] 2.3 Add `RevertApprovalModal`:
  - explanatory copy;
  - visitor and REQ ID;
  - a reason textarea with `maxLength=500`;
  - confirm disabled while the trimmed reason is empty;
  - a "Reverting…" busy label.
- [x] 2.4 Add a two-phase `form → confirm` flow to `RescheduleInvitationModal`, `EditInvitationModal` (summary of changed fields only; submit disabled when nothing changed) and `DelegateInvitationModal` (both `delegate` and `approve-and-delegate` modes). "Back" keeps the form input.

## 3. Board hook

- [x] 3.1 In `use-invitations-board.ts`, add `pendingApproveId`/`approvingId` with `requestApprove`, `confirmApprove` (step versus direct, as `approve()` does today) and `cancelApprove`, and add both to `isActionInProgress`.
- [x] 3.2 Add `pendingRevertId`/`revertingId` with `requestRevert`, `confirmRevert(reason)` and `cancelRevert`. On 409, close and refresh; on any other error, keep the dialog open. Show a success toast naming the visitor. Add both to `isActionInProgress`.
- [x] 3.3 Expose the new state and handlers from the hook and the `useAdminInvitations` / staff-dashboard wrappers.

## 4. Cards and pages

- [x] 4.1 Add a "Revert approval" icon button to `VisitRequestCard`'s icon row, last, for `status === 'approved'`. Give it the accessible name `Revert approval for <REQ ID>` and a tooltip, and add an icon if needed.
- [x] 4.2 Thread `onRevertClick` through `KanbanColumn` and `ResponsiveBoard`.
- [x] 4.3 In `staff-dashboard.tsx`:
  - wire `onApproveClick`, `onMoveToApproved` and `onDrop` to `requestApprove`;
  - render `ApproveInvitationModal` and `RevertApprovalModal` from hook state.
- [x] 4.4 In `admin-invitations.tsx`:
  - delete the page-local `pendingApproveId`;
  - use the hook's approve-confirm state instead;
  - render `RevertApprovalModal`.
- [x] 4.5 Add the "Approval reverted" note (time, reason, and name if present) to `VisitorInfoModal` when `status === 'submitted' && approvalRevertedAt`.

## 5. Verification

- [x] 5.1 Run the project typecheck and lint (`npm run build` / `npm run lint`). Do not run prettier.
- [ ] 5.2 Against a local API that has the VMSS_API change applied, walk both boards and check:
  - approve, step-approve, approve & delegate, delegate, deny, reject-step, reschedule, edit, check-out and revert each confirm before sending;
  - cancel sends nothing;
  - "Back" keeps form input;
  - a double-click sends one request;
  - polling pauses while a dialog is open.
- [ ] 5.3 Revert checks:
  - a manual-approved card moves to Requested;
  - a multi-step card returns to "Level 1/N · Pending";
  - a 409 after a QR check-in closes the dialog and refreshes;
  - Visitor Info shows the revert note, and the note disappears after re-approval.
- [ ] 5.4 Update `scripts/screenshot-pages.py` coverage or capture screenshots of the new dialogs if that's the team's review practice.
