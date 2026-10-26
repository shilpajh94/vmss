## MODIFIED Requirements

### Requirement: Filters narrow the board by purpose of visit and registration type
The system SHALL show these multi-select filters in the staff dashboard's search bar, in this order, each always visible with no separate "Filters" toggle:
- a Purpose of Visit filter, defaulting to "All purposes"
- a Registration Type filter (All types / Individual / Group)
- a Status filter, defaulting to "All statuses", offering Requested, Approved, Checked-in, Checked-out, Denied and Archived
- a Source filter, defaulting to "All sources", offering Staff Pre-Registration and Visitor Walk-in

The filters SHALL be the same shared component, options, labels and behaviour as the admin Invitations board's: themed dropdowns with checkbox options, a "Clear" action, and a summary of the first label plus "+N" when several are selected. A filter with several values SHALL match any of them; different filters SHALL combine with AND and with any active search text, across all columns. Each column's count badge SHALL reflect the combined filtered total. Selecting one or more Statuses SHALL load only those statuses' columns, and the other columns SHALL show zero. The filters SHALL only narrow the staff member's own relevant visit requests and SHALL never include visit requests the board would not show without them. A "Clear filters" action SHALL appear in the bar whenever any of the four filters has a selection. It SHALL reset all four filters and SHALL NOT clear the search text. Clearing a filter SHALL restore requests that only failed to match that criterion.

#### Scenario: Filtering by several purposes
- **WHEN** a staff member selects two Purpose of Visit values
- **THEN** visit requests matching either purpose are shown, in their existing columns

#### Scenario: Filtering by registration type
- **WHEN** a staff member selects a Registration Type filter value
- **THEN** only visit requests whose registration type matches that value are shown, in their existing columns

#### Scenario: Filtering by source
- **WHEN** a staff member selects "Visitor Walk-in" in the Source filter
- **THEN** only walk-in visit requests are shown, in their existing columns, and each column's count reflects the filtered total

#### Scenario: Filtering by several statuses
- **WHEN** a staff member selects "Archived" and "Denied" in the Status filter
- **THEN** only the Archived and Denied columns load visit requests and the other columns show zero

#### Scenario: Filters stay within the staff member's own requests
- **WHEN** a host who is not involved in an invitation at their branch selects any Status or Source filter value
- **THEN** that invitation is still not shown

#### Scenario: Filtering by purpose of visit
- **WHEN** a staff member selects a single Purpose of Visit filter value
- **THEN** only visit requests whose purpose of visit matches that value are shown, in their existing columns

#### Scenario: Filtering by status loads one column
- **WHEN** a staff member selects only "Archived" in the Status filter
- **THEN** only the Archived column loads visit requests and the other columns show zero

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
- **WHEN** every filter has no selection
- **THEN** no "Clear filters" action is shown

#### Scenario: Filters cleared
- **WHEN** a staff member clears all active filters
- **THEN** all visit requests matching only the current search text (if any) are shown again

#### Scenario: Export starts from the active status
- **WHEN** a staff member with export access has only "Approved" selected in the Status filter and opens the Export dialog
- **THEN** the dialog opens with "Approved" preselected as its status

#### Scenario: Export with several statuses selected
- **WHEN** a staff member has more than one value selected in any filter and opens the Export dialog
- **THEN** the dialog explains that export supports one value per filter and the Export action is disabled until the selection is narrowed
