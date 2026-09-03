## 1. Schema: scheduled visit time

- [x] 1.1 Add `preferredVisitDate` and `preferredVisitTime` (`z.string().min(1)`) to `VisitRequestSummarySchema` in `src/domain/entities/visit-request-summary-schema.ts`.
- [x] 1.2 Confirm `LIST_VISIT_REQUESTS` responses actually include these fields; if not yet available, mark them `.nullable()` instead and have the card hide the scheduled-time row when null. (Could not confirm against the live backend from this session — added as `.nullable()` per the fallback, and the card hides the scheduled-time row when either is null.)

## 2. Board hook: reschedule and delegate as dialogs

- [x] 2.1 In `src/presentation/hooks/use-invitations-board.ts`, add `pendingRescheduleId`, `requestReschedule(id)`, `cancelReschedule()` state, mirroring `pendingDenyId`/`requestDeny`/`cancelDeny`.
- [x] 2.2 Add `pendingDelegateId`, `requestDelegate(id)`, `cancelDelegate()` state the same way.
- [x] 2.3 Update `reschedule(...)` to clear `pendingRescheduleId` on success (keep it set on failure so the modal stays open).
- [x] 2.4 Update `delegate(...)` to clear `pendingDelegateId` on success (keep it set on failure so the modal stays open).
- [x] 2.5 Return the new state/handlers from the hook.

## 3. Modal components

- [x] 3.1 Create `src/presentation/components/invitation-board/RescheduleInvitationModal.tsx` wrapping `ui/Modal.tsx`, with date/time fields and a save action disabled until both are filled, following `DenyInvitationModal.tsx`'s shape.
- [x] 3.2 Create `src/presentation/components/invitation-board/DelegateInvitationModal.tsx` wrapping `ui/Modal.tsx`, with the role-scoped host `<select>` (moved from the card's inline panel) and a confirm action disabled until a host is selected.

## 4. Card: buttons + scheduled time, remove inline panels

- [x] 4.1 In `VisitRequestCard.tsx`, remove the `isExpanded && canReschedule` and `isExpanded && canDelegate` inline panels and their local `rescheduleDate`/`rescheduleTime`/`delegateUserId` state.
- [x] 4.2 Add a "Reschedule" button to the card footer, shown when `canReschedule`, calling a new `onRescheduleClick?: (id: string) => void` prop instead of opening inline.
- [x] 4.3 Add a "Delegate" button to the card footer, shown when `canDelegate`, calling a new `onDelegateClick?: (id: string) => void` prop instead of opening inline.
- [x] 4.4 Ensure both buttons stop click propagation so activating them does not also toggle card expansion.
- [x] 4.5 Render the scheduled visit date/time (`request.preferredVisitDate` / `request.preferredVisitTime`) on the card, alongside the existing submitted-at row, with a visible label distinguishing it from "submitted".

## 5. Wire buttons to modals at the board level

- [x] 5.1 Wherever `VisitRequestCard` is rendered (`KanbanColumn.tsx` / the board page(s) using `useInvitationsBoard`), pass `onRescheduleClick={requestReschedule}` and `onDelegateClick={requestDelegate}`.
- [x] 5.2 Render `<RescheduleInvitationModal>` and `<DelegateInvitationModal>` at the board level (next to the existing `<DenyInvitationModal>`), driven by `pendingRescheduleId` / `pendingDelegateId`, passing the matching request's `hostEmployees`/`roleNameById`/`detail` for the delegate host picker.
- [x] 5.3 Confirm `staff-dashboard` and `admin-invitations` pages (both consuming the shared board/card) pick up the new buttons and modals without page-specific changes.

## 6. Verification

- [ ] 6.1 Manually verify: Reschedule button appears only for `submitted`/`approved` requests, opens a modal, save disabled until both fields filled, success closes modal + refreshes + toasts, failure keeps modal open + toasts error.
- [ ] 6.2 Manually verify: Delegate button appears only when a current approval step exists, host picker is scoped to the step's role, success/failure behave as above.
- [ ] 6.3 Manually verify: card expansion still shows approval-step progress only, independent of the two new modals.
- [ ] 6.4 Manually verify: scheduled visit date/time renders on cards in both `/staff/dashboard` and `/admin/invitations`.

Not run this session: these require an authenticated session against a real backend (staff/admin login + visit requests with approval steps in various states), which wasn't available here. `tsc -b`, `oxlint`, `vite build`, and a dev-server smoke check (all edited/new modules transform and serve without error) all passed — see session notes. Recommend running this checklist against a live environment before merging.
