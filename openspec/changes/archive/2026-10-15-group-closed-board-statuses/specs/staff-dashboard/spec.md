## RENAMED Requirements

- FROM: `### Requirement: Visit requests are grouped into five status columns with live counts`
- TO: `### Requirement: Visit requests are grouped by status with live counts`

## MODIFIED Requirements

### Requirement: Visit requests are grouped by status with live counts
The system SHALL group visit requests by six statuses, in this order: Requested, Approved, Checked-in, Checked-out, Denied, Archived. Requested, Approved, and Checked-in are the working statuses. Checked-out, Denied, and Archived are the closed statuses. At `lg` and wider, each working status SHALL be its own column, and the three closed statuses SHALL share one Closed column after them (see "Closed statuses share one column on desktop"). Below `lg`, every status SHALL be its own tab (see responsive-layout "Invitation Boards Show One Status Column at a Time Below Desktop"). Every status SHALL show a count equal to the total number of visit requests in that status that match the active search and filters, as reported by the server. The count SHALL NOT be limited to the number of cards currently loaded.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully at 1536px wide
- **THEN** the board shows the Requested, Approved, Checked-in, and Closed columns, each request appears under its own status, and every status shows the server's total

#### Scenario: Count reflects the full total, not the loaded cards
- **WHEN** 250 visit requests are in the Requested status and only the first 20 have been loaded into the Requested column
- **THEN** the Requested column's count badge shows 250

#### Scenario: Checked-out visitors stay visible on the board
- **WHEN** a visitor on one of the staff member's visit requests checks out
- **THEN** after the next refresh or poll, that request appears under Checked-out in the Closed column instead of disappearing from the board, and the Checked-in and Checked-out counts reflect the move

### Requirement: Board columns keep a readable minimum width
At `lg` and wider, a board column SHALL NOT render narrower than 240px. When the columns cannot all fit at that width, the board SHALL scroll horizontally within its own region. The page itself SHALL NOT gain a horizontal scrollbar, and the page header, search field, filters, and every column header SHALL stay in place while the board scrolls vertically. When all columns fit, no horizontal scrollbar SHALL appear.

#### Scenario: Laptop width with the sidebar expanded
- **WHEN** a staff member views the board at 1366px wide with the sidebar expanded
- **THEN** all four columns fit side by side, each at least 240px wide, and no horizontal scrollbar appears

#### Scenario: Narrow desktop with the sidebar expanded
- **WHEN** a staff member views the board at 1280px wide with the sidebar expanded
- **THEN** each column is at least 240px wide, the board scrolls horizontally within its own area, and the page does not scroll horizontally

#### Scenario: Room freed by collapsing removes the scroll
- **WHEN** a staff member at 1280px wide collapses the sidebar
- **THEN** all four columns fit side by side and no horizontal scrollbar appears on the board

## ADDED Requirements

### Requirement: Closed statuses share one column on desktop
At `lg` and wider, the board SHALL show the Checked-out, Denied, and Archived statuses in a single column, titled "Closed", after the Checked-in column. Its header SHALL show the sum of the three statuses' server totals. Below the header, a segmented switcher SHALL list Checked-out, Denied, and Archived, in that order, each with its own server total. The switcher SHALL be exposed to assistive technology as a tab list, and exactly one status SHALL be selected at a time. The column body SHALL show the selected status's cards with the same paging, empty-state message, card actions, and Visitor Info behaviour as that status had as its own column.

Switching statuses SHALL NOT refetch any status, reset any other column's scroll position, or change the search or filters. Statuses that are not selected SHALL NOT request further pages. Every count SHALL keep updating on manual and background refreshes whichever status is selected.

When the status filter is set to Checked-out, Denied, or Archived, the switcher SHALL select that status. Otherwise, the switcher SHALL select the status last chosen on this board in this browser, remembered across reloads and new sessions. If no choice is stored, or stored preferences cannot be read, it SHALL select Checked-out. Status columns SHALL NOT offer any control to collapse or hide them.

#### Scenario: Default view
- **WHEN** a staff member opens the board for the first time at 1536px wide
- **THEN** the Closed column's header shows the combined total, its switcher shows Checked-out, Denied, and Archived with their counts, and Checked-out is selected with its cards listed

#### Scenario: Switching to Denied
- **WHEN** a staff member selects Denied in the Closed column's switcher
- **THEN** the column lists Denied cards, each offering only Visitor info, and the Requested, Approved, and Checked-in columns keep their scroll positions

#### Scenario: Status filter drives the switcher
- **WHEN** a staff member picks "Archived" in the status filter
- **THEN** the Closed column selects Archived and lists the matching archived visits, and the other closed statuses show a count of zero

#### Scenario: Choice is remembered
- **WHEN** a staff member selects Denied and then reloads the page
- **THEN** the Closed column opens with Denied selected

#### Scenario: Counts update while another status is selected
- **WHEN** Denied is selected and a background refresh moves a visit from Checked-in to Checked-out
- **THEN** the Checked-out count in the switcher and the Closed header total both update, and Denied stays selected

#### Scenario: Phones and tablets keep separate tabs
- **WHEN** a staff member opens the board at 390px wide
- **THEN** the status tabs list Requested, Approved, Checked-in, Checked-out, Denied, and Archived as six separate tabs, with no Closed grouping

## REMOVED Requirements

### Requirement: Status columns can be collapsed on desktop
**Reason**: Per-column collapse toggles cluttered the board, and a collapsed status looked like it had disappeared. Grouping the three closed statuses into one Closed column frees the same width by default, with nothing hidden and nothing for users to set up.
**Migration**: None for users. The feature was never released. The stored `vmss:ui:board:<board>:collapsed-columns` value is no longer read, and stale entries are harmless.
