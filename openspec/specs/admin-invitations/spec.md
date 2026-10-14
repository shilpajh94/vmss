# admin-invitations Specification

## Purpose

The admin-invitations capability is the Super Admin's Invitations screen at `/admin/invitations`: it gives an admin the same organisation-wide Kanban view and approve/reschedule/deny actions the staff dashboard gives staff, so an admin can monitor and act on visit requests without needing the staff-facing screen.

## Requirements

### Requirement: Admin section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Invitations page, and SHALL redirect to `/admin/login` instead of rendering when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/admin/invitations`
- **THEN** the system redirects to `/admin/login` and does not render the page

### Requirement: Admin sidebar and top bar render with "Invitations" active
The system SHALL render, for an authenticated session, the Admin sidebar with "Invitations" shown as the active item, and the Admin top bar showing the Invitations-specific description and the signed-in staff member's name and role.

#### Scenario: Admin views the Invitations page
- **WHEN** an authenticated admin's Invitations page finishes loading
- **THEN** the sidebar shows "Invitations" marked active and the top bar shows the signed-in staff member's name and role

### Requirement: Invitations are grouped into five status columns with live counts
The system SHALL group invitations into five columns, in this order: Requested, Approved, Checked-in, Checked-out, Denied. Each column SHALL show a count badge equal to the server's total number of invitations in that status matching the active search and filters, using the same board component as the staff dashboard. The count SHALL NOT be limited to the number of cards currently loaded. When a status filter is selected, only that status's column SHALL load invitations; the other columns SHALL show zero. Every status the status filter offers, including Checked-out, SHALL have a matching column.

#### Scenario: Invitations load successfully
- **WHEN** the invitations list loads successfully
- **THEN** each invitation appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Checked-out invitations appear in their own column
- **WHEN** the invitations list loads and some invitations have the status `checked_out`
- **THEN** those invitations appear in the Checked-out column, which sits between Checked-in and Denied, and its count badge shows the server's total of checked-out invitations matching the active search and filters

#### Scenario: Empty column
- **WHEN** a status column has zero invitations
- **THEN** the system shows an empty-state message instead of any cards

#### Scenario: Status filter limits loading to one column
- **WHEN** an admin selects the "Approved" status filter
- **THEN** only the Approved column loads invitations, and the Requested, Checked-in, Checked-out, and Denied columns show a count of zero and their empty state

#### Scenario: Checked-out status filter loads the Checked-out column
- **WHEN** an admin selects the "Checked-out" status filter
- **THEN** only the Checked-out column loads invitations and shows the server's total, and the other four columns show a count of zero and their empty state

### Requirement: Search filters visible invitations by visitor name or tracking ID
The system SHALL, as the admin types in the search field, show only invitations whose visitor name or tracking ID contains the entered text (case-insensitive), across all columns.

#### Scenario: Search narrows the board
- **WHEN** an admin enters text in the search field
- **THEN** only invitations whose visitor name or tracking ID contains that text remain visible, in their existing columns

### Requirement: Refresh reloads the invitations list
The system SHALL, when the refresh action is activated, re-fetch every column's already-loaded pages, the role list, and the employee directory, and re-render the board with the latest data. A column the admin has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Admin refreshes the board
- **WHEN** an admin activates the refresh action
- **THEN** the system re-fetches the underlying data and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** an admin has loaded 60 cards into a column and activates the refresh action
- **THEN** that column still holds up to 60 cards after the refresh and is not scrolled back to the top

### Requirement: List load failure is reported without crashing
The system SHALL, when the invitations list fails to load, show an error message on the page, trigger an error notification, and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the invitations list fails to load
- **THEN** the system shows an error message, triggers an error notification, and lets the admin retry

### Requirement: Card expand, approve, reschedule, and deny behave the same as the staff dashboard
The system SHALL provide on this page the same card behaviours specified for the staff-dashboard capability's board, unchanged:
- activating a card opens Visitor Info
- the "Level X/Y · Pending" approval badge
- card-face Approve/Deny buttons and drag-to-approve (direct or step-based)
- drag-to-deny, with a required reason (direct or step-based)
- the Visitor info, Reschedule, Edit, and Delegate icon buttons and the modals they open

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same success and failure notifications

#### Scenario: Activating a card opens Visitor Info
- **WHEN** an admin clicks a card on the Invitations board outside its buttons
- **THEN** the Visitor Info modal opens for that invitation, and the card does not expand

### Requirement: Invitations board pins its column headers and loads columns lazily
The admin Invitations board SHALL keep each column's header visible while its cards scroll. It SHALL load each column in pages of 20 as the admin scrolls, without duplicates, and SHALL stop requesting pages once a column is fully loaded. This is the same behaviour the staff dashboard defines in "Status column headers stay visible while cards scroll" and "Columns load visit requests lazily in pages".

#### Scenario: Scrolling a long column
- **WHEN** an admin scrolls to the end of the 20 cards loaded in the Requested column at 1280px wide
- **THEN** the "Requested" header and count stay visible, a loading indicator appears at the end of the column, and the next 20 invitations are appended

#### Scenario: Search change restarts columns
- **WHEN** an admin has scrolled a column past its first page and then changes the search text
- **THEN** every column reloads from its first page with the new search applied

### Requirement: Checked-in cards on the admin board offer the same manual check-out
The system SHALL offer, on every card in the admin Invitations board's Checked-in column, the same confirmed "Check Out" action specified for the staff-dashboard capability's board, with the same confirmation, success, conflict, and failure behaviour. Admins SHALL always see the action on Checked-in cards on this page.

#### Scenario: Admin checks out a visitor from the Invitations board
- **WHEN** an admin activates "Check Out" on a Checked-in card on the Invitations page and confirms
- **THEN** the visitor is checked out, a success notification is shown, and after the board reloads the card appears in the Checked-out column

#### Scenario: Check Out with the Checked-in status filter active
- **WHEN** the admin board's status filter is set to Checked-in and an admin checks a visitor out from that column
- **THEN** after the reload the card no longer appears in the Checked-in column, and the Checked-in count decreases by one

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
