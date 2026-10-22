## ADDED Requirements

### Requirement: The staff Invitations page uses the admin page layout
The staff Invitations page (`/staff/dashboard`) SHALL use the same page layout as the admin Invitations page:
- a persistent top bar above the page content;
- a title row with "Invitations" and, for a Reception session, the "Export" button with its icon and label at the right end;
- the search and filter bar;
- the board, which is the only region that scrolls from `lg` up, each column under its pinned header.

At the same viewport width, the title row, filter bar and board SHALL have the same font sizes, control heights, spacing and alignment on both pages. They SHALL differ only in each section's accent colour and in Export visibility (admins on the admin page, Reception on the staff page). The loading state SHALL read "Loading invitations…" on both pages.

#### Scenario: Same layout at desktop width
- **WHEN** a Reception user opens `/staff/dashboard` and an admin opens `/admin/invitations`, both at 1440px wide
- **THEN** both pages show the top bar, then an "Invitations" title row with Export at the right, then the filter bar, then the board, at the same vertical positions

#### Scenario: Export in the title row
- **WHEN** a Reception user opens the staff Invitations page
- **THEN** the "Export" button, with its label, is at the right end of the "Invitations" title row, and neither the top bar nor the filter bar contains it

#### Scenario: Host sees no Export
- **WHEN** a staff member without the Reception role opens the staff Invitations page
- **THEN** the title row shows only "Invitations"

#### Scenario: Loading text
- **WHEN** the staff Invitations board is loading
- **THEN** it shows "Loading invitations…"

## MODIFIED Requirements

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated non-Reception session, a sidebar (brand mark, "Invitations" / "My actions" navigation with "Invitations" selected, and a "Help & Support" link), the shared staff top bar, and a main workspace containing the "Invitations" title row, the search and filter bar, and the invitations kanban board. For an authenticated Reception session, the system SHALL instead render the Reception sidebar (see `reception-dashboard`) with "Invitations" marked active, alongside the same top bar and main workspace.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated, non-Reception staff member's dashboard finishes loading
- **THEN** the staff sidebar (with "Invitations" selected), the staff top bar, the "Invitations" title row, the search bar, and the kanban board are all visible

#### Scenario: Authenticated Reception user views the dashboard
- **WHEN** an authenticated Reception user's dashboard finishes loading
- **THEN** the Reception sidebar (with "Invitations" marked active), the staff top bar, the "Invitations" title row, the search bar, and the kanban board are all visible

### Requirement: Workspace header shows the signed-in staff member
The system SHALL display the signed-in staff member's name and role in the staff top bar, retrieved from the current-staff-user API. The top bar SHALL be laid out like the admin top bar: on the left, a section title ("Reception Desk" for a Reception-role session, "Staff Workspace" otherwise) with the page description beneath it from `md` up, or the current page's navigation label ("Invitations", "My actions") below `md`; on the right, the shared refresh control, the notification bell, the user's avatar, name and role, and "Sign out".

#### Scenario: Current user loads successfully
- **WHEN** the dashboard loads and the current-staff-user request succeeds
- **THEN** the top bar displays that staff member's name and role

#### Scenario: Reception session title
- **WHEN** a Reception user opens the staff Invitations page at 1440px wide
- **THEN** the top bar's title reads "Reception Desk" with the page description beneath it

#### Scenario: Phone shows the page name
- **WHEN** a staff member opens the staff Invitations page at 360px wide
- **THEN** the top bar shows "Invitations" next to the navigation menu button, and the page has no horizontal scroll

### Requirement: Refresh reloads the visit-requests list
The system SHALL present exactly one refresh control on the staff Invitations page: the shared refresh control in the staff top bar, showing when the board was last updated ("Updated just now", "Updated 2m ago"), as on the admin top bar. The page SHALL NOT render its own Refresh button. When that control is activated, the system SHALL re-fetch, for every column, the pages that column has already loaded, and re-render the board with the latest data. A column the staff member has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Only one refresh control is shown
- **WHEN** the dashboard finishes loading
- **THEN** exactly one refresh control is visible on the page, in the top bar, with an "Updated …" time beside it from `md` up

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates the refresh control
- **THEN** the system re-fetches every column's loaded pages and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** a staff member has loaded 60 cards into the Requested column, scrolled down, and activates the refresh control
- **THEN** the Requested column still holds up to 60 cards after the refresh and is not scrolled back to the top

### Requirement: The workspace header and search bar are compact
The system SHALL render the staff Invitations page's title row as the admin Invitations page does: "Invitations" on the left and, for a Reception session, the "Export" button with its label on the right. The page description SHALL appear in the top bar, not in the title row. The search field SHALL be the same 40px height as the filters. From `lg` up, the search field and the four filters SHALL sit on one row, with the search field taking the remaining width. Below `lg` they SHALL wrap as they do today, with no horizontal overflow.

#### Scenario: Desktop filter row
- **WHEN** the staff dashboard is viewed at a desktop width (`lg` or wider)
- **THEN** the search field and the Purpose, Registration Type, Status and Source filters appear on a single row at equal height, below the "Invitations" title row

#### Scenario: Narrow screen
- **WHEN** the staff dashboard is viewed at 360px wide
- **THEN** the search field and filters stack without horizontal page scroll
