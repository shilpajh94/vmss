## MODIFIED Requirements

### Requirement: Search filters visible requests by visitor, host, or REQ ID
The system SHALL, as the staff member types in the search field, show only visit requests whose visitor name or tracking ID contains the entered text (case-insensitive), across all columns. The search field's placeholder SHALL read "Search visitor, tracking ID...", the same wording as the admin Invitations board, and SHALL NOT suggest that the host is searched. The search SHALL be applied by the server to every column's results, so matches beyond the cards already loaded are found, and each column's count badge SHALL reflect the searched total.

#### Scenario: Search narrows the board
- **WHEN** a staff member enters text in the search field
- **THEN** only visit requests whose visitor name or tracking ID contains that text are shown, in their existing columns, and each column's count shows how many matches exist in that status

#### Scenario: Search finds a request that was not loaded yet
- **WHEN** a staff member searches for the tracking ID of a request that is older than every card loaded in its column
- **THEN** that request appears in its column

#### Scenario: Search is cleared
- **WHEN** a staff member clears the search field
- **THEN** each column reloads from its first page with no search applied

#### Scenario: Placeholder matches the admin board
- **WHEN** the staff dashboard's search field is empty
- **THEN** it shows the placeholder "Search visitor, tracking ID..."

### Requirement: Filters narrow the board by purpose of visit and registration type
The system SHALL show these filters in the staff dashboard's search bar, in this order, each always visible with no separate "Filters" toggle:
- a Purpose of Visit filter, defaulting to "All purposes"
- a Registration Type filter (All types / Individual / Group)
- a Status filter, defaulting to "All statuses", offering Requested, Approved, Checked-in, Checked-out, Denied and Archived
- a Source filter, defaulting to "All sources", offering Staff Pre-Registration and Visitor Walk-in

The options and labels SHALL be the same as the admin Invitations board's. When any filter is selected, the system SHALL show only visit requests matching all selected criteria, combined with any active search text, across all columns. Purpose, Registration Type and Source SHALL be applied by the server to every column's results, and each column's count badge SHALL reflect the filtered total. Selecting a Status SHALL load only that status's column, and the other columns SHALL show zero, as on the admin board. The filters SHALL only narrow the staff member's own relevant visit requests and SHALL never include visit requests the board would not show without them. A "Clear filters" action SHALL appear in the bar whenever any of the four filters differs from its default. It SHALL reset all four filters and SHALL NOT clear the search text. Clearing a filter SHALL restore requests that only failed to match that criterion.

#### Scenario: Filtering by purpose of visit
- **WHEN** a staff member selects a Purpose of Visit filter value
- **THEN** only visit requests whose purpose of visit matches that value are shown, in their existing columns

#### Scenario: Filtering by registration type
- **WHEN** a staff member selects a Registration Type filter value
- **THEN** only visit requests whose registration type matches that value are shown, in their existing columns

#### Scenario: Filtering by source
- **WHEN** a staff member selects "Visitor Walk-in" in the Source filter
- **THEN** only walk-in visit requests are shown, in their existing columns, and each column's count reflects the filtered total

#### Scenario: Filtering by status loads one column
- **WHEN** a staff member selects "Archived" in the Status filter
- **THEN** only the Archived column loads visit requests and the other columns show zero

#### Scenario: Filters stay within the staff member's own requests
- **WHEN** a host who is not involved in an invitation at their branch selects any Status or Source filter value
- **THEN** that invitation is still not shown

#### Scenario: Combined with search
- **WHEN** a staff member has both a search term and a filter active
- **THEN** only visit requests matching both the search term and the active filter(s) are shown

#### Scenario: Changing a filter restarts every column from its first page
- **WHEN** a staff member has scrolled a column past its first page and then changes a filter
- **THEN** every column reloads from its first page with the new filter applied

#### Scenario: Clear filters resets every filter
- **WHEN** a staff member has a Purpose and a Source filter selected and a search term entered, and activates "Clear filters"
- **THEN** all four filters return to their defaults, the search term is kept, and "Clear filters" is no longer shown

#### Scenario: Clear filters hidden at defaults
- **WHEN** every filter is at its default value
- **THEN** no "Clear filters" action is shown

#### Scenario: Filters cleared
- **WHEN** a staff member clears all active filters
- **THEN** all visit requests matching only the current search text (if any) are shown again

#### Scenario: Export starts from the active status
- **WHEN** a staff member with export access has "Approved" selected in the Status filter and opens the Export dialog
- **THEN** the dialog opens with "Approved" preselected as its status

### Requirement: The workspace header and search bar are compact
The system SHALL render the staff dashboard's "Invitations" title as a compact title row, and the search field at the same 40px height as the filters. On wide screens the search field and all four filters SHALL sit on one row, with the search field taking the remaining width. "Clear filters", when shown, SHALL follow on that row when it fits and otherwise wrap to the next line without clipping. The Export button is not part of this bar; it sits in the title row. Below `lg` the controls SHALL wrap or stack, with no horizontal overflow.

#### Scenario: Desktop filter row
- **WHEN** the staff dashboard is viewed at 1440px wide
- **THEN** the search field and the Purpose, Registration Type, Status and Source filters appear on a single row at equal height

#### Scenario: Extra controls wrap instead of clipping
- **WHEN** the staff dashboard is viewed at 1024px wide with a filter set, so "Clear filters" shows
- **THEN** every filter and "Clear filters" are fully visible, wrapping to a second line if needed

#### Scenario: Narrow screen
- **WHEN** the staff dashboard is viewed at 360px wide
- **THEN** the search field and filters stack without horizontal page scroll
