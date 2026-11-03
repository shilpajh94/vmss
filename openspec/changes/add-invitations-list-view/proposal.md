## Why

The admin and staff Invitations pages only offer the Kanban board. With many visits a board is hard to scan, compare and sort. A table-style list gives a dense, readable alternative while the board stays the familiar default.

## What Changes

- Add a **Board / List** view switch to the Invitations pages (`/admin/invitations` and `/staff/invitations`). **Board remains the default**; the choice is remembered per portal for the browser.
- Add a **list view**: a table with one row per invitation showing visitor (avatar + name), tracking ID, status chip, purpose, host/point of contact, visit date and time, registration type (individual/group) and source, plus the same row actions the board cards offer (view info, approve, deny, reschedule, edit, check out…), permission-gated exactly as on the board.
- The list reuses the board's search, filters and loaded data; no new API call and no change to backend contracts. Rows are sorted newest visit first and grouped by "Load more" per status the way columns load today.
- Below `lg` the list renders as stacked cards instead of a wide table.
- Non-goals: server-side sorting/paging across statuses, new filters, bulk actions, calendar-page changes.

## Capabilities

### New Capabilities
- `invitation-list-view`: A Board/List view switch and a table-style list of invitations shared by the admin and staff Invitations pages.

### Modified Capabilities

## Impact

- `src/presentation/components/invitation-board/`: new `InvitationViewToggle` and `InvitationListView` (+ row component).
- `src/presentation/pages/admin-invitations/admin-invitations.tsx` and `src/presentation/pages/staff-invitations/staff-invitations.tsx`: render the toggle and choose board or list.
- `use-stored-state` for the remembered choice. No domain, data-layer, infrastructure or composition-root changes expected.
- Open point: `VisitRequestSummary` has no host or branch name, so the host column uses the point-of-contact label the cards already compute; confirm the column set when implementing.
