## 0. Prerequisite

- [x] 0.1 Confirm the companion API change `VMSS_API` → `grant-reception-checkout-permission` is implemented, and that the local tenant has been upgraded (Reception holds `invitations:checkout`)

## 1. Data layer

- [x] 1.1 Add `CHECK_OUT_INVITATION: { endpoint: "/invitations/:id/check-out", method: "PATCH", hasToken: true }` to `src/data/api/api-endpoints.ts`
- [x] 1.2 Add `checkOut(id: string, idempotencyKey: string): Promise<void>` to the `VisitRequestSummaryRepository` interface in `src/data/repositories/visit-request-summary-repository.ts`
- [x] 1.3 Implement it in `src/infrastructure/visit-request-summary-repository.ts`, mirroring `deny`: pass the `Idempotency-Key` header, use `InvitationActionResultSchema`, and throw `new Error(response.message)` when `!response.success`
- [x] 1.4 Create `src/data/use-cases/check-out-invitation.ts` (`CheckOutInvitationUseCase`, same shape as `DenyInvitationUseCase`)
- [x] 1.5 Wire `checkOutInvitationUseCase` into `src/composition-root.ts` (type entry, lazy resolver, getter), following `denyInvitationUseCase`

## 2. Board hook

- [x] 2.1 In `src/presentation/hooks/use-invitations-board.ts`, add `pendingCheckOutId` and `checkingOutId` state, and add both to `isActionInProgress`
- [x] 2.2 Add `requestCheckOut(id)`, `cancelCheckOut()` and `confirmCheckOut()`. `confirmCheckOut` generates `crypto.randomUUID()`, calls the use case, shows a success toast with `"<visitor name> checked out."` (look the name up from the loaded column data), shows an error toast with the `Error.message`, always clears the pending/checking state, and calls `loadDashboard({ silent: true })`
- [x] 2.3 Derive and return `canCheckOut = Boolean(currentUser?.isAdmin || currentUser?.isReception)`, plus the pending request's `visitorName`/`trackingId` for the modal

## 3. UI

- [x] 3.1 Create `src/presentation/components/invitation-board/CheckOutVisitorModal.tsx`, modelled on `DenyInvitationModal` without the reason field. The title is "Check Out Visitor", the message reads "Check out <name> (<trackingId>)? This marks the visit as ended.", the buttons are Cancel and a primary "Check Out" that is disabled and reads "Checking out…" while `isCheckingOut`
- [x] 3.2 Add an optional `onCheckOutClick?: (id: string) => void` prop to `VisitRequestCard.tsx` and render a "Check Out" button after Visitor Info when it is set, in the same button style family. Include it in the action-row visibility condition
- [x] 3.3 Thread `onCheckOutClick` through `KanbanColumn.tsx` to each card
- [x] 3.4 In `staff-dashboard.tsx` and `admin-invitations.tsx`, pass `onCheckOutClick={column.status === 'checked_in' && canCheckOut ? requestCheckOut : undefined}` and render `<CheckOutVisitorModal …/>` next to the Deny modal

## 4. Verification

- [x] 4.1 `npm run build` (type check plus build) and `npm run lint` are clean. Do not run prettier (this repo has none)
- [x] 4.2 Manual check as Reception on `/staff/dashboard`: the button shows only on Checked-in cards; cancel does nothing; confirm moves the card to Checked-out and updates both counts; the confirm button is disabled while in flight
- [x] 4.3 Manual check as Host: no Check Out button. As Admin on `/admin/invitations`: the button works, including with the Checked-in status filter active
- [x] 4.4 Manual conflict check: open the dialog, check the same visitor out via the QR check-out endpoint, then confirm. An error toast appears and the card reloads into Checked-out
- [x] 4.5 Check the mobile layout (below `lg`): Visitor Info and Check Out sit side by side without overflow
