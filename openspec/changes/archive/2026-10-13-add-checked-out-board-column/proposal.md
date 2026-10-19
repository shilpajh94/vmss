## Why

The invitations board has four columns: Requested, Approved, Checked-in and Denied. When a visitor checks out, their invitation moves to `checked_out` and disappears from the board. Front office and hosts therefore can't see who has already left, which is the other half of the "who's here today" picture. The admin board's status filter already offers "Checked-out", but selecting it empties every column because no column maps to that status. The API already supports `GET /invitations?status=checked_out`, so the fix is entirely in the web app.

## What Changes

- Add a fifth board column, **Checked-out**, between Checked-in and Denied (in lifecycle order). Like every other column, it is one server query (`status=checked_out`), paged 20 at a time, with a count badge that shows the server total.
- The column applies to both boards that use the shared board hook: the admin Invitations board (`/admin/invitations`, every invitation) and the staff/reception Visits board (`/staff/dashboard`, the user's own invitations).
- On the admin board, selecting the "Checked-out" status filter now loads the Checked-out column instead of leaving every column empty.
- Checked-out cards are read-only: they offer **Visitor Info** only, the same as Checked-in and Denied cards. They can't be dragged and are not drop targets.
- The column uses a neutral/muted accent, matching the existing `checked_out` status pill in the Visitor Info modal. It shows the empty-state message "No checked-out visits". No board column filters by date, so the wording avoids "today".
- Below `lg`, the mobile status selector gains a Checked-out tab automatically, because it already lists every column. Its behaviour does not change.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `admin-invitations`: the board grows from four columns to five, and a Checked-out status filter now loads that column instead of emptying the board.
- `staff-dashboard`: the Visits board grows from four columns to five.

## Impact

- **Code (VMMS_WEB only):**
  - `src/presentation/hooks/use-paged-board-columns.ts`: `BoardStatus`, `BOARD_STATUSES`, the API status map and the initial column state.
  - `src/presentation/hooks/use-invitations-board.ts`: `BOARD_STATUS_COLUMNS`.
  - `src/presentation/components/invitation-board/KanbanColumn.tsx`: accent classes for `checked_out`.
  - `src/presentation/pages/admin-invitations/admin-invitations.tsx` and `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`: empty-state messages.
  - The related tests for these files.
- **API:** no change. `InvitationStatus.checked_out` is already a valid `status` filter on `GET /invitations`.
- **Load:** each board load, refresh and poll makes one more list request (five instead of four).
- **Layout:** five columns side by side at `lg` widths. The board container already scrolls horizontally (`overflow-x-auto`), so narrow desktops stay usable.
