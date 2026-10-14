## Why

Cards in the board's Checked-in column offer only **Visitor Info**. A visitor who leaves without scanning their QR code at the exit therefore stays "checked in" indefinitely. That inflates the Checked-in count and corrupts the "who's inside" picture the emergency report depends on. Front office needs a way to close the visit by hand. The API already supports this (`PATCH /api/v2/invitations/{id}/check-out`), so this change is mainly UI work. The companion API change, `VMSS_API` → `grant-reception-checkout-permission`, lets Reception call that endpoint.

## What Changes

- Every card in the **Checked-in** column gains a **Check Out** button next to Visitor Info, for staff who are allowed to check visitors out: Admin and Reception.
- Activating it opens a confirmation dialog that names the visitor and tracking ID. On confirm, the web app calls the check-out endpoint, shows a success toast, and reloads the board, so the card moves from Checked-in to Checked-out and both counts update.
- While the request is in flight, the dialog's confirm button is disabled and shows "Checking out…". A double click or a network retry can't check the visitor out twice, because each confirmation sends one `Idempotency-Key`.
- If the API rejects the request (the visitor already checked out by QR scan, `409`; no permission, `403`; or any other failure), an error toast shows the API's message, and the board reloads so the card reflects the server state.
- Hosts and Security don't see the button. Approved, Requested, Checked-out and Denied cards are unchanged.
- The rule applies to both boards built on the shared board hook: the admin Invitations board (`/admin/invitations`) and the staff/reception Visits board (`/staff/dashboard`).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-dashboard`: Checked-in cards offer a confirmed manual Check Out action to Admin and Reception users.
- `admin-invitations`: the admin board inherits the same Check Out action on Checked-in cards.

## Impact

- **Code (VMMS_WEB):**
  - `src/data/api/api-endpoints.ts`: `CHECK_OUT_INVITATION` (`PATCH /invitations/:id/check-out`).
  - `src/data/repositories/visit-request-summary-repository.ts` and `src/infrastructure/visit-request-summary-repository.ts`: `checkOut(id, idempotencyKey)`.
  - `src/data/use-cases/check-out-invitation.ts` (new), wired in `src/composition-root.ts`.
  - `src/presentation/hooks/use-invitations-board.ts`: request/confirm/cancel check-out state, busy flag for polling, and `canCheckOut` derived from the current user.
  - `src/presentation/components/invitation-board/VisitRequestCard.tsx` and `KanbanColumn.tsx`: the `onCheckOutClick` prop and button.
  - `src/presentation/components/invitation-board/CheckOutVisitorModal.tsx` (new).
  - `src/presentation/pages/staff-dashboard/staff-dashboard.tsx` and `src/presentation/pages/admin-invitations/admin-invitations.tsx`: pass the handler to the Checked-in column only, and render the modal.
- **API:** no change to the endpoint. The companion API change must be deployed first, or Reception gets a 403 toast.
- **Audit/notifications:** handled server-side by the existing endpoint (`invitation_checked_out` audit entry, host push notification).
