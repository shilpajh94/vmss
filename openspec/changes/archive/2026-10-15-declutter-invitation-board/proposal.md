## Why

The Invitations board is the most-used screen for staff, reception, and
admins, and on a typical 1920px desktop it is crowded. The docked sidebar
takes a fixed 280px (260px staff), and the six status columns (Requested,
Approved, Checked-in, Checked-out, Denied, Archived) split what's left with
`flex-1` and a 170px floor. That leaves each column about 230px wide, so
visitor names, meta lines ("Interview · Unassigned …"), and the Approve/Deny
buttons are truncated. Columns with few or no cards (Checked-out: 1,
Archived: 0) get exactly as much width as Requested with 126. This gets worse
as tenants add volume and on 1366–1536px laptops, which reception desks
commonly use.

## What Changes

- **Collapsible desktop sidebar.** On desktop (≥1024px), the Admin, Staff,
  and Reception sidebars get a collapse toggle that shrinks them to a narrow
  icon rail (~72px). The rail shows only the nav icons (each with an
  accessible name and a hover/focus tooltip) and the compact brand mark.
  Expanding restores the full sidebar. The choice is remembered per browser,
  so it survives reloads and route changes. It applies shell-wide, not just
  to the board, because the sidebar is part of the persistent shell. Below
  1024px nothing changes: the existing off-canvas drawer always shows the
  full sidebar.
- **Collapsible board columns.** Each status column header on the desktop
  board gets a collapse toggle. A collapsed column becomes a slim vertical
  strip showing its label (rotated) and its count badge, and gives its width
  to the other columns. Activating the strip expands it again. Collapsed
  state is remembered per browser and per board (admin vs staff).
  Drag-and-drop onto a collapsed Approved/Denied column still works, with
  the same confirmation dialogs.
- **Readable minimum column width.** Expanded columns never shrink below a
  readable width (240px). When the expanded columns don't fit, the board
  scrolls horizontally inside its own region, never the page, instead of
  squeezing and truncating cards.
- Below 1024px, the existing one-column-at-a-time status tabs are unchanged.
  Column collapse is a desktop-only control.

Non-goals: auto-collapsing empty columns. The board refreshes in the
background, so columns would collapse and expand on their own as counts move
between 0 and 1, shifting the layout under the user's cursor. Also out of
scope: changing card content or density, server-side persistence of layout
preferences, and any API change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `app-shell`: adds a requirement that the docked desktop sidebar can be
  collapsed to an icon rail and that the choice persists. The fixed-sidebar
  requirement now allows the docked sidebar to be in either state.
- `staff-dashboard`: adds requirements for collapsible status columns and a
  minimum readable column width with contained horizontal scrolling.
- `admin-invitations`: the admin board adopts the same column-collapse and
  minimum-width behaviour, stated by reference like the existing
  pinned-header requirement.

## Impact

- **Code (VMMS_WEB only):** `AppShell.tsx`, `nav-drawer-context.tsx` (or a
  sibling sidebar-collapse context), `AdminSidebar.tsx`,
  `DashboardSidebar.tsx`, `ReceptionSidebar.tsx`, `BrandLogo.tsx` (compact
  mark if one doesn't exist), `invitation-board/ResponsiveBoard.tsx`,
  `invitation-board/KanbanColumn.tsx`, and the two board pages
  (`staff-dashboard.tsx`, `admin-invitations.tsx`) to pass a board key for
  persistence.
- **Storage:** new per-browser `localStorage` keys for the sidebar and column
  preferences, read and written defensively (falls back to expanded when
  storage is unavailable).
- **API:** none. **Dependencies:** none new.
- **Verification:** no unit-test tier exists in VMMS_WEB. Verify via `npm run
  lint`, `npm run build`, and browser QA/screenshots at 1280, 1536, and
  1920px, plus the 800px drawer path.
