## Why

The Visits board (`/staff/dashboard`, and `/admin/invitations` which reuses the same card) feels cramped. Every action a card allows is a full-width button stacked one below another. A Requested card can carry Visitor Info, Reschedule, Approve, Deny and Edit, so each column fits only about one and a half cards at a time. The host label also wraps onto two lines ("Unassigned — Front / Office"), and the scheduled date is pushed to the bottom of the card below all the buttons. The header and filter bar above the board add more height on top of that. Staff mostly scan the board and act on the decision for a request, so the rarely used actions are taking up the space that cards should have.

## What Changes

- **Primary actions only on the card face.** Each card keeps as buttons only the actions that decide the request in its column: Approve + Deny side by side, or Approve & Delegate / Approve + Deny on Reception's step, on actionable Requested cards. Checked-in cards keep Check Out for Admin/Reception. Approved, Checked-out and Denied cards show no buttons on the card face.
- **Secondary actions become a row of compact icon buttons** along the bottom of the card: Visitor info, Reschedule, Edit and Delegate. Each icon appears under exactly the conditions where its button appears today, has a tooltip with its name, and is keyboard- and touch-operable. Every action stays visible on the card; there is no hidden menu.
- **Clicking a card opens Visitor Info.** This replaces the current click-to-expand behaviour. **BREAKING (UX)**: cards no longer expand. The approval-progress line that expansion showed already appears on the collapsed card as the "Level X/Y · Pending: …" badge, so nothing is lost. A `?invitationId=` deep link (for example, from a push notification) now opens that visit's Visitor Info modal instead of expanding its card.
- **Denser card layout.** The visitor name and REQ ID sit beside the avatar. Purpose and host share one truncated meta line, with the full text available on hover. The scheduled date/time moves up, directly under the meta line. Padding and gaps are tighter.
- **Tighter columns.** Column header bars are shorter and the gaps between columns and cards are smaller. There are still five columns, and the pinned headers and lazy loading are unchanged.
- **Slimmer staff-dashboard header.** The "Visits" title is smaller and sits with its subtitle in a compact block. The search field matches the filter dropdowns' 40px height, and on desktop search and filters share one row. The admin Invitations page header is already compact and is left as is.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `staff-dashboard`: card activation opens Visitor Info instead of expanding the card. Approval progress is described on the card badge only. Visitor info, Reschedule, Delegate and Edit become icon buttons rather than full-width labelled buttons. The card layout requirement adds the single meta line and the position of the scheduled time.
- `admin-invitations`: the "same as staff dashboard" requirement no longer mentions card expansion and points at the new card interaction instead.

## Impact

- **Depends on `visit-card-schedule-actions`**: that change is implemented but not yet archived (only manual-verification tasks remain). Its delta adds the Reschedule/Delegate button requirements that this change modifies, so archive it before this one.
- `src/presentation/components/invitation-board/VisitRequestCard.tsx`: restructured layout; labelled primary buttons plus an icon row; card click calls the Visitor Info handler.
- New `src/presentation/components/ui/IconActionButton.tsx` (an icon button with an accessible name and a hover/focus tooltip). It reuses existing icons from `src/presentation/components/icons.tsx`.
- `src/presentation/components/invitation-board/KanbanColumn.tsx`: spacing; expansion props removed.
- `src/presentation/hooks/use-invitations-board.ts`: `expandedId`/`toggleExpand` retired; the deep link opens Visitor Info. Detail prefetch for Requested/Approved cards is unchanged.
- `src/presentation/pages/staff-dashboard/Components/WorkspaceHeader.tsx` and `SearchActionBar.tsx`: compact header and a one-row search/filter bar.
- `staff-dashboard.tsx` and `admin-invitations.tsx`: stop passing the expansion props.
- No API changes. VMSS_API is untouched.
