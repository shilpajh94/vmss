## Context

Both boards render through `useInvitationsBoard` → `ResponsiveBoard` → `KanbanColumn` → `VisitRequestCard`. Card actions are opt-in props: a page passes a handler only for the columns where the action applies (for example `onMoveToDenied={column.status === 'requested' ? requestDeny : undefined}`), and the card renders the button only when it receives the handler. Deny is the closest precedent: the hook holds `pendingDenyId`/`denyingId`, a modal (`DenyInvitationModal`) confirms, a use case (`DenyInvitationUseCase`) calls `HttpVisitRequestSummaryRepository.deny`, and the hook then toasts and calls `loadDashboard`.

The web app does not know the caller's permission codes. `StaffUser` carries only `isAdmin`/`isReception`, derived from branch-role names in `staff-auth-repository.ts`. The API endpoint `PATCH /invitations/{id}/check-out` returns the updated invitation in the standard envelope, returns `409` if the invitation isn't `checked_in`, and accepts an optional `Idempotency-Key`.

## Goals / Non-Goals

**Goals:**
- A Check Out button on Checked-in cards for Admin and Reception, confirmed through a dialog, following the Deny flow's structure.

**Non-Goals:**
- No bulk "check out everyone" action, and no end-of-day auto checkout.
- No check-out from inside the Visitor Info modal. It could be added later by reusing the same hook callback.
- No permission-code plumbing to the web app. Role-name gating is consistent with how Reception-only UI is already decided.
- No optimistic card move. The board reloads from the server instead.

## Decisions

**1. Gate visibility in the hook as `canCheckOut = currentUser?.isAdmin || currentUser?.isReception`, and let pages pass `onCheckOutClick` only to the `checked_in` column when `canCheckOut` is true.**
This keeps the card unaware of roles, the same way it is unaware of column status today. The API remains the real authority: if a custom role or stale grant makes the guess wrong, the user gets a 403 toast, not a silent failure.
*Alternative:* always show the button and rely on the 403. Rejected because the user chose Admin + Reception, and showing hosts a button that always fails is poor UX.

**2. Use a dedicated `CheckOutVisitorModal` rather than reusing `ConfirmDialog`.**
`ConfirmDialog` has no busy/disabled state and always styles the confirm button as `bg-danger`. Check-out is a routine, non-destructive action, and it needs the "Checking out…" disabled state (the double-submit scenario). The new modal mirrors `DenyInvitationModal` without the reason field. It takes `visitorName`/`trackingId` for the message, plus `isCheckingOut`, `onConfirm` and `onCancel`. The confirm button uses the primary/secondary-accent style, not danger.
*Alternative:* extend `ConfirmDialog` with `isConfirming` and `tone` props. This is reasonable, but it touches every existing caller's visual contract. The dedicated modal is smaller and matches the Deny precedent.

**3. Generate one `Idempotency-Key` (`crypto.randomUUID()`) per confirmation, in the hook, and pass it through the use case to the repository header.**
Disabling the button stops UI double clicks, but it doesn't cover a request that times out on a flaky network and gets retried. The API caches the response per key (`vmss:{tenant}:idempotency:{key}`), so a retry returns the same result instead of a `409`. The key belongs to the confirmation, not the invitation, so a later legitimate re-check-out after a re-entry gets a fresh key.

**4. On any outcome other than cancel, close the modal and call `loadDashboard({ silent: true })`. Toast success as `"<Name> checked out."`, and on error toast the `Error.message` from the API envelope.**
A `409` means someone else (usually a QR exit scan) already moved the card, so reloading shows the truth. On other failures the reload is harmless, and the card stays in Checked-in as the spec requires. Both `pendingCheckOutId` and `checkingOutId` join `isActionInProgress`, so the 15 s poll doesn't re-render the board under an open dialog.

**5. The repository method mirrors `deny`.** It calls `makeRequest` with `API_ENDPOINTS.CHECK_OUT_INVITATION`, `pathParams: { id }`, `headers: { 'Idempotency-Key': key }` and `InvitationActionResultSchema`, and throws `new Error(response.message)` when `!response.success`. No new response schema is needed, because the board doesn't read the returned invitation.

## Risks / Trade-offs

- [Role-name gating diverges from real permissions (for example, a custom "Front Desk" role granted `invitations:checkout`)] → That user won't see the button. This is acceptable for now. If it comes up, expose permission codes on `/auth/me` and switch the gate, which is a separate change.
- [The web change ships before the API change] → Reception sees the button but gets a 403 toast. Mitigate by deploying the API first (see the companion change's Migration Plan).
- [Six-plus buttons don't fit on narrow cards] → Checked-in cards have only Visitor Info today, so adding one button gives two `flex-1` buttons, which fit at every breakpoint.
