## Why

The API is gaining `PATCH /invitations/{id}/revert-approval` (VMSS_API
change `add-invitation-approval-revert`), so a mistakenly approved visit can
be sent back for review. The boards need a way to trigger it. Mis-clicks
are also the reason these approvals happen at all, and confirmation is
inconsistent today:

- The Admin board confirms Approve, but the Staff Dashboard approves the
  moment the button is pressed.
- Reschedule, Edit, Delegate and Approve & Delegate submit straight from
  their forms.

Every action that changes an invitation should ask "are you sure?" before
it is sent.

## What Changes

- Add a **Revert approval** icon button on Approved cards on both boards.
  It opens a dialog that requires a reason (1–500 chars) and names the
  visitor and REQ ID. On confirm it calls the new endpoint, refreshes the
  board (the card moves back to Requested) and shows a success
  notification. On failure it shows the server's message.
- **Every state-changing invitation action is confirmed before its request
  is sent**:
  - approve and approve-step (on both boards; the Staff Dashboard gains the
    dialog it lacks today);
  - Approve & Delegate and Delegate;
  - Deny and Reject-step;
  - Revert approval;
  - Check Out;
  - Reschedule and Edit.

  Reason-dialog actions (deny, revert) and check-out already present a
  dedicated confirm step. Form actions (reschedule, edit, delegate, approve
  & delegate) gain a confirm step after the form is filled. It summarizes
  what will change, and Cancel goes back to the form with its input kept.
- Confirm buttons disable and show progress while the request is in
  flight, so a double-click sends one request. Background board refresh
  pauses while any confirmation is open or in flight. This also fixes the
  Admin board's approve confirmation, which currently isn't counted as
  "busy".
- Visitor Info shows an "Approval reverted" note (when, by whom, reason)
  on a Requested invitation whose approval was reverted.
- Add a `revertApproval` repository method, a use-case and an endpoint
  constant. The invitation entity gains `approvalRevertedAt`,
  `approvalRevertedByUserId` and `approvalRevertReason`, all optional.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `staff-dashboard`:
  - new Revert-approval requirement;
  - new "every invitation action is confirmed" requirement;
  - approve (drop or button) now requires confirmation;
  - the icon-row requirement gains Revert approval;
  - Visitor Info shows the revert note.
- `admin-invitations`: the "behave the same as the staff dashboard"
  requirement now includes revert and the universal confirmation.

## Impact

- **Code**:
  - `presentation/hooks/use-invitations-board.ts`: revert flow, approve
    confirmation moved into the hook, form-confirm state and the busy flag.
  - `presentation/components/invitation-board/*`:
    - new `RevertApprovalModal`;
    - a confirm step in `RescheduleInvitationModal`,
      `EditInvitationModal` and `DelegateInvitationModal`;
    - the icon button in `VisitRequestCard`;
    - the revert note in `VisitorInfoModal`.
  - `presentation/components/ui/ConfirmDialog.tsx`: gains `tone` and
    `isBusy` props.
  - `pages/staff-dashboard/staff-dashboard.tsx` and
    `pages/admin-invitations/admin-invitations.tsx`.
  - `data/api/api-endpoints.ts`, the `VisitRequestSummaryRepository`
    interface and its implementation, a new use-case, `composition-root.ts`
    and the invitation entity and schema.
- **Dependency**: requires the API change to be deployed first. Until then
  the Revert button gets a 404/405 and shows an error notification, with
  nothing broken.
- **Permissions**: the web has no permission codes, only
  `isAdmin`/`isReception`. Revert is shown to every board user, and the
  API's 403 is surfaced as an error notification. By default only
  `security` lacks the permission, and Security doesn't act on these
  boards.
