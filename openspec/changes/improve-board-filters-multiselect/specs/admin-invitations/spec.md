## MODIFIED Requirements

### Requirement: Search and filters sit in one inline bar matching the staff dashboard
The system SHALL render, above the admin Invitations board, a single bar laid out like the staff dashboard's search bar. It SHALL contain, in this order:
- a search field the same 40px height as the filters, taking the remaining width
- a Purpose of Visit multi-select filter, defaulting to "All purposes", whose options are the same purposes the staff dashboard offers
- a Registration Type multi-select filter (All types / Individual / Group)
- a Status multi-select filter, defaulting to "All statuses", offering Requested, Approved, Checked-in, Checked-out, Denied and Archived
- a Source multi-select filter, defaulting to "All sources", offering Staff Pre-Registration and Visitor Walk-in

Each filter SHALL be a themed dropdown (not the browser's native select menu): a 40px trigger showing the filter's icon, a summary and a chevron, that opens a floating panel with one checkbox row per option and a "Clear" action. The panel SHALL close on outside click or Escape, and the trigger and options SHALL be operable by keyboard with correct ARIA roles. The trigger summary SHALL read the default label when nothing is selected, the option's label when one is selected, and the first label plus a "+N" count when several are selected.

Every filter SHALL always be visible; the page SHALL NOT have a separate "Filters" toggle or pop-open filter panel. On wide screens the controls SHALL sit on one row. On narrow screens they SHALL wrap or stack without horizontal page scroll. A filter with several values selected SHALL match invitations having ANY of those values; different filters SHALL combine with AND and with the search text. Every column SHALL be narrowed accordingly on the server side of each request, and each column's count SHALL reflect the combined filtered total. A "Clear filters" action SHALL appear in the bar whenever any filter has a selection, and SHALL reset all four filters, without clearing the search text.

#### Scenario: All filters visible without a toggle
- **WHEN** an admin opens the Invitations page
- **THEN** the search field and the Purpose, Registration Type, Status, and Source filters are all visible in one bar, and there is no "Filters" toggle button

#### Scenario: Selecting several purposes
- **WHEN** an admin ticks two Purpose of Visit options
- **THEN** invitations matching either purpose are shown, merged in each column (each value's own newest-first order interleaved), each column's count is the sum across the two purposes, and the trigger reads "<first label> +1"

#### Scenario: Several filters combine with AND
- **WHEN** an admin selects two purposes and the "Visitor Walk-in" source
- **THEN** only walk-in invitations with either purpose are shown

#### Scenario: Selecting every option equals no filter
- **WHEN** an admin ticks every option of a filter
- **THEN** that filter behaves as unfiltered and the trigger reads its default "All …" label

#### Scenario: Status multi-select loads several columns
- **WHEN** an admin selects "Approved" and "Checked-in" in the Status filter
- **THEN** only the Approved and Checked-in columns load invitations and the other columns show zero

#### Scenario: Dismissing the panel
- **WHEN** an admin has a filter panel open and presses Escape or clicks outside it
- **THEN** the panel closes and the selection is kept

#### Scenario: Clear filters resets every filter
- **WHEN** an admin has several Purpose values and a Source filter selected and a search term entered, and activates "Clear filters"
- **THEN** all four filters return to their defaults, the search term is kept, and "Clear filters" is no longer shown

#### Scenario: Wide screen layout
- **WHEN** the Invitations page is viewed at 1440px wide
- **THEN** the search field and all four filter triggers sit on one row

#### Scenario: Filtering by purpose of visit
- **WHEN** an admin selects a single Purpose of Visit filter value
- **THEN** only invitations whose purpose of visit matches that value are shown, in their existing columns, and each column's count reflects the filtered total

#### Scenario: Status filter still loads one column
- **WHEN** an admin selects only "Approved" in the Status filter
- **THEN** only the Approved column loads invitations and the other columns show zero, as before

#### Scenario: Narrow screen layout
- **WHEN** the Invitations page is viewed at 360px wide
- **THEN** the search field and filters stack or wrap with no horizontal page scroll, and an opened filter panel stays within the viewport width

#### Scenario: Archived is a status option
- **WHEN** an admin opens the Status filter
- **THEN** "Archived" is listed after "Denied", and selecting it loads only the Archived column
