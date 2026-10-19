## Context

Both boards (`staff-dashboard.tsx`, `admin-invitations.tsx`) render
`KanbanColumn` → `VisitRequestCard`. All of their action logic lives in
`presentation/hooks/use-invitations-board.ts`.

Each action follows a `requestX(id)`, then a `pendingXId` state, then a
modal, then `confirmX()`, then a use-case, then
`VisitRequestSummaryRepository`. Approve is the exception:

- the hook's `approve()` calls the API directly;
- only the Admin page wraps it in `ApproveInvitationModal`, using
  page-local `pendingApproveId`, which isn't part of the hook's
  `isActionInProgress`;
- the Staff Dashboard wires `approve` straight to the button.

`usePolling` skips ticks while `isActionInProgress` is true. There is no
permission-code model in the web, only `isAdmin`/`isReception`. The
contract comes from VMSS_API `add-invitation-approval-revert`:

- `PATCH /api/v1/invitations/{id}/revert-approval` with body `{ reason }`;
- the response is the standard envelope holding the invitation;
- the new output fields are `approvalRevertedAt`,
  `approvalRevertedByUserId` and `approvalRevertReason`;
- errors are 409, 403 and 404.

## Goals / Non-Goals

**Goals:**
- One confirmation pattern used everywhere, with all confirm state owned by
  the hook so both pages get identical behavior and polling sees it.

**Non-Goals:**
- Permission-aware hiding of Revert, since the web has no permission codes
  (see proposal Impact).
- Confirmations on non-invitation admin CRUD pages, which already use
  `ConfirmDialog` for deletes.
- Undo toasts or time-delayed sends as an alternative to confirmation.

## Decisions

### 1. Move approve confirmation into the hook
Add a `pendingApproveId` / `requestApprove(id)` / `confirmApprove()` /
`cancelApprove()` to `use-invitations-board.ts`, following the deny and
check-out shape. `confirmApprove` keeps today's branch: the step endpoint
if there is a `currentApprovalStep`, otherwise the direct endpoint. Both
pages wire `onApproveClick`, `onMoveToApproved` and `onDrop` to
`requestApprove`, and render `ApproveInvitationModal` from hook state.

The Admin page's local `pendingApproveId` is deleted. Adding the new
`pendingApproveId` and `approvingId` to `isActionInProgress` fixes polling
interrupting an open approve dialog.

*Alternative*: copy the Admin page's local state into the Staff Dashboard.
Rejected because it duplicates logic and leaves polling unaware of it.

### 2. Generalize `ConfirmDialog` instead of a modal per action
Add optional props to `ui/ConfirmDialog.tsx`:

- `tone?: 'danger' | 'primary' | 'success'`, default `'danger'` so the
  existing CRUD-page usages are unchanged;
- `isBusy?: boolean` and `busyLabel?: string`, which disable confirm and
  show progress;
- `children?: ReactNode`, for summary rows rendered under `message`.

The form-confirm steps and the approve dialog use it. The existing
`ApproveInvitationModal` becomes a thin wrapper over it (or is replaced
by it).

`DenyInvitationModal` and `CheckOutVisitorModal` already *are*
confirmations and stay as they are. The new `RevertApprovalModal` copies
`DenyInvitationModal`, with a reason textarea limited to 500 characters
and confirm disabled while the trimmed reason is empty, because it needs
the same reason field.

### 3. Form actions use a two-phase modal, not a second stacked modal
`RescheduleInvitationModal`, `EditInvitationModal` and
`DelegateInvitationModal` (both modes) get an internal
`phase: 'form' | 'confirm'`:

- Submitting the form switches to `confirm` and renders the summary inside
  the same `Modal`, with the visitor, REQ ID and the changed values.
- "Back" returns to `form`, keeping the form's state because the component
  never unmounted.
- "Confirm" calls the existing `onConfirm`.

The existing `isRescheduling`/`isDelegating`/`isEditing` flags drive the
busy label.

*Alternative*: open a `ConfirmDialog` on top of the form modal. Rejected
because stacked modals fight `use-focus-trap` and the backdrop, and
preserving input across close and reopen would need lifted state.

For Edit, the summary lists only the fields whose values differ from the
initial values. If nothing changed, submit stays disabled, so an empty
edit isn't confirmable.

### 4. Revert wiring
- `api-endpoints.ts`: `revertApproval: (id) => /invitations/${id}/revert-approval`.
- The repository interface and its implementation get
  `revertApproval(id, reason)` (`PATCH`, `{ reason }`).
- A new `RevertInvitationApprovalUseCase` is registered in
  `composition-root.ts`.
- The hook gets `pendingRevertId`, `revertingId`, `requestRevert`,
  `confirmRevert(reason)` and `cancelRevert`, all included in
  `isActionInProgress`.
- **Error handling**: on 409 the hook closes the dialog and refreshes,
  matching the check-out "already left" case. On any other error the
  dialog stays open.
- `VisitRequestCard` shows the icon when `status === 'approved'`, in the
  last position of the icon row. It uses a counter-clockwise-arrow icon,
  added to `components/icons` if one doesn't exist.

### 5. Entity fields and the Visitor Info note
Add the three optional fields to the invitation zod schema and entity. They
are `.nullish()` so older API responses still parse.

`VisitorInfoModal` renders the note when `status === 'submitted' &&
approvalRevertedAt`. The reverting user's name is resolved only if the
detail payload already carries one. Otherwise the note shows the time and
reason only, with no extra fetch.

## Risks / Trade-offs

- **[Risk]** The web ships before the API, so Revert gets a 404 or 405. →
  It goes through the normal error toast and keeps the dialog open; ship
  the API first.
- **[Trade-off]** The extra click on every action slows down heavy
  approvers. → Accepted by request. The shared `Modal` has no Enter/Escape
  handling today, so confirming is a click; keyboard shortcuts would be a
  separate, app-wide `Modal` change.
- **[Risk]** Revert is shown to Security-only users who lack the permission.
  → They get a 403 toast. Security doesn't normally act on these boards.
- **[Risk]** The VMMS_WEB repo has no prettier config. → Don't run prettier;
  format by hand to match the surrounding code.

## Migration Plan

Deploy after the VMSS_API change. No data migration is needed. To roll
back, revert the web deploy; the API endpoint is harmless when unused.
