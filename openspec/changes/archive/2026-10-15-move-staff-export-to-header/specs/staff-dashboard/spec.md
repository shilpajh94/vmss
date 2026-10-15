## ADDED Requirements

### Requirement: The staff Export button sits in the Invitations title row
For a signed-in user who holds the Reception role, the staff dashboard SHALL show its "Export" button at the right of the "Invitations" title row, the same placement and full "Export" label (download icon and word) as the admin Invitations page. The Export button SHALL NOT appear inside the search and filter bar, which SHALL contain only the search field, the Purpose of Visit, Registration Type, Status and Source filters, and, when any filter is set, "Clear filters". Staff members without the Reception role SHALL NOT see an Export button anywhere on the dashboard. Activating it SHALL open the same Export invitations dialog as before, preselected with the board's current Status filter.

#### Scenario: Export is in the title row, not the bar
- **WHEN** a Reception user opens the staff dashboard at 1440px wide
- **THEN** the Export button appears at the right of the "Invitations" title row, and the filter bar contains no Export button

#### Scenario: Filter bar matches the admin layout
- **WHEN** a Reception user at 1440px wide selects a Source filter
- **THEN** the search field and the four filters stay on one row, and "Clear filters" is the only control on the line below them, as on the admin Invitations board

#### Scenario: A host sees no Export button
- **WHEN** a staff member without the Reception role opens the staff dashboard
- **THEN** neither the title row nor the filter bar shows an Export button

#### Scenario: Export still opens the dialog with the active status
- **WHEN** a Reception user with "Approved" selected in the Status filter activates the title row's Export button
- **THEN** the Export invitations dialog opens with "Approved" preselected
