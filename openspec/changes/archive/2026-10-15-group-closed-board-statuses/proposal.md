## Why

`declutter-invitation-board` added a collapsible sidebar (keep), a 240px
column floor (keep), and a collapse toggle on every status column. That last
part is the problem. Six extra toggles add noise to the busiest screen in the
product. A collapsed column looks like a status that disappeared ("where did
Denied go?"). And every user has to work out their own layout before the
board stops feeling crowded.

The underlying problem is that the board gives equal width to two different
kinds of status:

- **Working statuses**: Requested, Approved, and Checked-in. Staff act on
  these all day (approve, deny, check out, reschedule, delegate).
- **Closed statuses**: Checked-out, Denied, and Archived. These are mostly
  look-ups. Checked-out and Denied cards offer only Visitor info. Archived
  no-shows can still be rescheduled or edited, but there are only a handful
  of them.

Grouping the closed statuses fixes the crowding by default, with no toggles
and no per-user setup.

## What Changes

- **One "Closed" column on desktop.** From `lg` up, the board shows four
  columns: Requested, Approved, Checked-in, and Closed. The Closed header
  shows the combined total. Under the header, a segmented switcher lists
  Checked-out, Denied, and Archived, each with its own count. The selected
  status's cards fill the column, with the same paging, empty states, and
  card actions as today. Every status stays one click away with its count
  always visible, so nothing is hidden.
- **The switcher follows the status filter and remembers the last choice.**
  Choosing Denied in the status filter selects Denied in the Closed column.
  Otherwise the column opens on the last status picked on that board (staff
  and admin remember separately), and on Checked-out the first time.
- **BREAKING (UI, unreleased):** remove the per-column collapse toggles,
  collapsed strips, and their stored preference. This change was implemented
  but never released.
- **Keep** the collapsible sidebar rail and the 240px column minimum from
  `declutter-invitation-board`. With four columns, the board fits without
  sideways scrolling at 1366px even with the sidebar expanded (about 246px
  per column). At 1280px it fits once the sidebar is collapsed.
- **Below `lg`:** no change. The six status tabs stay as they are.

Non-goals: changing which statuses exist, card content, server queries
(each status is still its own paged query), or the phone/tablet tabs.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `staff-dashboard`:
  - The status grouping becomes "three working columns plus a Closed
    column" on desktop.
  - Removes "Status columns can be collapsed on desktop".
  - Updates the minimum-width scenarios for four columns.
  - Renames the outdated "five status columns" requirement. The board has
    had six statuses since Archived was added.
- `admin-invitations`:
  - Same grouping on the admin board, including how the status filter
    drives the Closed switcher.
  - Removes the column-collapse requirement.
  - Renames the outdated "five status columns" requirement.

## Impact

- **Code (VMMS_WEB):** `invitation-board/ResponsiveBoard.tsx` (desktop
  grouping), a new `invitation-board/ClosedStatusesColumn.tsx`,
  `invitation-board/KanbanColumn.tsx` (remove collapse, add a header-less
  embedded mode), `hooks/use-invitations-board.ts` (closed-status
  constant), and the two board pages.
- **Ordering:** `declutter-invitation-board` must be archived before this
  change is archived. This change's REMOVED requirements are the ones that
  change adds to the main specs. Implementation can start before then.
- **API / dependencies:** none.
- **Verification:** `npm run lint`, `npm run build`, and Playwright QA
  (same harness as `declutter-invitation-board`) at 1920, 1366, and 1280px
  with the sidebar expanded and collapsed, plus 800/390px.
