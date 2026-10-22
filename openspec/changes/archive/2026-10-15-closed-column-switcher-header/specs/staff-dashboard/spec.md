## MODIFIED Requirements

### Requirement: Closed statuses share one column on desktop
At `lg` and wider, the board SHALL show the Checked-out, Denied, and Archived statuses in a single column after the Checked-in column. The column SHALL have no title row and no combined total. Its header SHALL be a segmented switcher listing Checked-out, Denied, and Archived, in that order, each with its own server total. The switcher SHALL sit where the other columns' headers sit and SHALL be the same height as they are, so that the first card in every column starts at the same vertical position. The switcher SHALL show each status's full label at every column width the board allows. It SHALL be exposed to assistive technology as a tab list named "Closed status", and exactly one status SHALL be selected at a time. The column body SHALL show the selected status's cards with the same paging, empty-state message, card actions, and Visitor Info behaviour as that status had as its own column.

Switching statuses SHALL NOT refetch any status, reset any other column's scroll position, or change the search or filters. Statuses that are not selected SHALL NOT request further pages. Every count SHALL keep updating on manual and background refreshes whichever status is selected.

When the status filter is set to Checked-out, Denied, or Archived, the switcher SHALL select that status. Otherwise, the switcher SHALL select the status last chosen on this board in this browser, remembered across reloads and new sessions. If no choice is stored, or stored preferences cannot be read, it SHALL select Checked-out. Status columns SHALL NOT offer any control to collapse or hide them.

#### Scenario: Default view
- **WHEN** a staff member opens the board for the first time at 1536px wide
- **THEN** the fourth column's header is the switcher showing Checked-out, Denied, and Archived with their counts, with no "Closed" title or combined total, and Checked-out is selected with its cards listed

#### Scenario: Switcher header lines up with the other headers
- **WHEN** a staff member views the board at 1366px wide with the sidebar expanded
- **THEN** the switcher header is the same height as the Requested, Approved, and Checked-in headers, the first card in all four columns starts at the same vertical position, and "Checked-out", "Denied", and "Archived" are each shown in full

#### Scenario: Switching to Denied
- **WHEN** a staff member selects Denied in the switcher
- **THEN** the column lists Denied cards, each offering only Visitor info, and the Requested, Approved, and Checked-in columns keep their scroll positions

#### Scenario: Status filter drives the switcher
- **WHEN** a staff member picks "Archived" in the status filter
- **THEN** the switcher selects Archived and the column lists the matching archived visits, and the other closed statuses show a count of zero

#### Scenario: Choice is remembered
- **WHEN** a staff member selects Denied and then reloads the page
- **THEN** the switcher opens with Denied selected

#### Scenario: Counts update while another status is selected
- **WHEN** Denied is selected and a background refresh moves a visit from Checked-in to Checked-out
- **THEN** the Checked-out count in the switcher updates and Denied stays selected

#### Scenario: Phones and tablets keep separate tabs
- **WHEN** a staff member opens the board at 390px wide
- **THEN** the status tabs list Requested, Approved, Checked-in, Checked-out, Denied, and Archived as six separate tabs, with no grouping
