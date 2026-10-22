## ADDED Requirements

### Requirement: Status columns can be collapsed on desktop
At `lg` and wider, each status column header SHALL include a collapse toggle labelled "Collapse <status> column" or "Expand <status> column" according to its state, exposing its expanded/collapsed state to assistive technology. A collapsed column SHALL render as a narrow vertical strip, no wider than 56px, showing the column's label and its server total count, and the other expanded columns SHALL widen to share the freed space. Activating anywhere on the strip SHALL expand the column again.

Collapsing or expanding a column SHALL NOT refetch, reset, or reorder any column, and SHALL NOT change the search or filters. A collapsed column SHALL NOT request further pages while collapsed. Its count SHALL keep updating on manual and background refreshes. When the column is expanded again, it SHALL show its cards without the user having to re-scroll other columns.

A collapsed Approved or Denied column SHALL remain a drop target for dragged cards. Dropping a card on it SHALL trigger the same approve or deny-with-reason flow as dropping on the expanded column, and the strip SHALL show the same drag-over highlight.

Which columns are collapsed SHALL be remembered in the current browser, separately for the staff board and the admin board, across reloads and new sessions. When no choice is stored, or stored preferences cannot be read, every column SHALL start expanded. Columns SHALL NOT collapse or expand on their own, including when a column's count changes to or from zero. Below `lg`, the status-tab layout SHALL be unchanged: no collapse toggles are shown, and every status remains selectable as a tab regardless of its stored desktop state.

#### Scenario: Collapsing a sparse column
- **WHEN** a staff member at 1536px wide activates "Collapse Archived column" while Archived has 0 cards
- **THEN** Archived becomes a narrow strip showing "Archived" and "0", and the remaining five columns widen to fill the board

#### Scenario: Expanding a collapsed column
- **WHEN** a staff member activates the collapsed Checked-out strip
- **THEN** the Checked-out column renders at full width with its header, count, and cards, and the other columns keep their scroll positions

#### Scenario: Count keeps updating while collapsed
- **WHEN** the Checked-out column is collapsed and a background refresh brings its total from 1 to 2
- **THEN** the strip's count reads 2 and the column stays collapsed

#### Scenario: Dropping on a collapsed Denied column
- **WHEN** a staff member drags a Requested card onto the collapsed Denied strip
- **THEN** the strip highlights during the drag, and on drop the deny dialog asking for a reason opens, exactly as for the expanded column

#### Scenario: Layout survives a reload
- **WHEN** a staff member collapses Checked-out and Archived and then reloads the page
- **THEN** the board renders with those two columns already collapsed

#### Scenario: Collapse state does not leak into the phone tabs
- **WHEN** a staff member who collapsed Archived on desktop opens the board at 390px wide
- **THEN** the Archived tab is present and selectable, and its column renders normally when chosen

### Requirement: Board columns keep a readable minimum width
At `lg` and wider, an expanded status column SHALL NOT render narrower than 240px. When the expanded columns cannot all fit at that width, the board SHALL scroll horizontally within its own region. The page itself SHALL NOT gain a horizontal scrollbar, and the page header, search field, filters, and every column header SHALL stay in place while the board scrolls vertically. When all columns fit, no horizontal scrollbar SHALL appear.

#### Scenario: Narrow desktop with the sidebar expanded
- **WHEN** a staff member views the board at 1280px wide with the sidebar expanded and all six columns expanded
- **THEN** each column is at least 240px wide, the board scrolls horizontally within its own area to reveal the remaining columns, and the page does not scroll horizontally

#### Scenario: Room freed by collapsing removes the scroll
- **WHEN** a staff member at 1920px wide collapses the sidebar
- **THEN** all six expanded columns fit side by side and no horizontal scrollbar appears on the board
