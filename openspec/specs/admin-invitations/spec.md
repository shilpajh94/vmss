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
The system SHALL provide, on this page, the same card-expansion (with step-progress and pending-approver display), drag-to-approve (direct or step-based), drag-to-deny (with a required reason, direct or step-based), and reschedule behaviors specified for the staff-dashboard capability's board, unchanged.

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same success and failure notifications

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
