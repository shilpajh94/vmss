## ADDED Requirements

### Requirement: Search and filters sit in one inline bar matching the staff dashboard
The system SHALL render, above the admin Invitations board, a single bar laid out like the staff dashboard's search bar. It SHALL contain, in this order:
- a search field the same 40px height as the filters, taking the remaining width
- a Purpose of Visit filter, defaulting to "All purposes", whose options are the same purposes the staff dashboard offers
- a Registration Type filter (All types / Individual / Group)
- a Status filter, defaulting to "All statuses", offering Requested, Approved, Checked-in, Checked-out and Denied
- a Source filter, defaulting to "All sources", offering Staff Pre-Registration and Visitor Walk-in

Every filter SHALL always be visible; the page SHALL NOT have a separate "Filters" toggle or pop-open filter panel. On wide screens the controls SHALL sit on one row. On narrow screens they SHALL wrap or stack without horizontal page scroll. Selecting a filter SHALL narrow every column on the server, combined with the search text and other filters, and each column's count SHALL reflect the filtered total. A "Clear filters" action SHALL appear in the bar whenever any filter differs from its default, and SHALL reset all four filters, without clearing the search text.

#### Scenario: All filters visible without a toggle
- **WHEN** an admin opens the Invitations page
- **THEN** the search field and the Purpose, Registration Type, Status, and Source filters are all visible in one bar, and there is no "Filters" toggle button

#### Scenario: Filtering by purpose of visit
- **WHEN** an admin selects a Purpose of Visit filter value
- **THEN** only invitations whose purpose of visit matches that value are shown, in their existing columns, and each column's count reflects the filtered total

#### Scenario: Status filter still loads one column
- **WHEN** an admin selects "Approved" in the Status filter
- **THEN** only the Approved column loads invitations and the other columns show zero, as before

#### Scenario: Clear filters resets every filter
- **WHEN** an admin has a Purpose and a Source filter selected and a search term entered, and activates "Clear filters"
- **THEN** all four filters return to their defaults, the search term is kept, and "Clear filters" is no longer shown

#### Scenario: Wide screen layout
- **WHEN** the Invitations page is viewed at 1440px wide
- **THEN** the search field and all four filters sit on a single row at equal height

#### Scenario: Narrow screen layout
- **WHEN** the Invitations page is viewed at 360px wide
- **THEN** the search field and filters stack or wrap with no horizontal page scroll
