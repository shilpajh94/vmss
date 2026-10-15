# staff-dashboard Specification

## Purpose

The staff-dashboard capability is the authenticated staff landing screen at `/staff/dashboard`: it shows every visit request for the organisation grouped by status so staff can review activity at a glance.

## Requirements

### Requirement: Dashboard requires an authenticated session
The system SHALL check for a staff auth token before rendering the dashboard, and SHALL redirect to `/staff/login` instead of rendering the dashboard when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to `/staff/dashboard`
- **THEN** the system redirects to `/staff/login` and does not render the dashboard

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to `/staff/dashboard`
- **THEN** the system renders the dashboard

### Requirement: Dashboard renders the sidebar, workspace header, and kanban board
The system SHALL render, for an authenticated non-Reception session, a sidebar (brand mark, "All visitors" / "My actions" navigation with "All visitors" selected, and a "Help & Support" link) and a main workspace containing the header, search bar, and visit-requests kanban board. For an authenticated Reception session, the system SHALL instead render the Reception sidebar (see `reception-dashboard`) with "Visits" marked active, alongside the same main workspace.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated, non-Reception staff member's dashboard finishes loading
- **THEN** the staff sidebar, the "Visits" workspace header, the search bar, and the kanban board are all visible

#### Scenario: Authenticated Reception user views the dashboard
- **WHEN** an authenticated Reception user's dashboard finishes loading
- **THEN** the Reception sidebar (with "Visits" marked active), the "Visits" workspace header, the search bar, and the kanban board are all visible

### Requirement: Other sidebar navigation items are visible but not yet functional
The system SHALL render the "Help & Support" link per the design, but SHALL NOT navigate anywhere when it is activated.

#### Scenario: Inert nav item activated
- **WHEN** a staff member activates "Help & Support"
- **THEN** the current view does not change

### Requirement: "My actions" opens the Register Visitor wizard
The system SHALL, when a staff member activates "My actions" in the sidebar, navigate to the Register Visitor wizard's first step.

#### Scenario: Staff opens My actions
- **WHEN** an authenticated staff member activates "My actions" in the sidebar
- **THEN** the system navigates to the Register Visitor wizard, showing the Visitor Info step

### Requirement: Workspace header shows the signed-in staff member
The system SHALL display the signed-in staff member's name and role in the workspace header, retrieved from the current-staff-user API.

#### Scenario: Current user loads successfully
- **WHEN** the dashboard loads and the current-staff-user request succeeds
- **THEN** the header displays that staff member's name and role

### Requirement: Sign out ends the session and returns to login
The system SHALL, when "Sign out" is activated, clear the stored auth token and navigate to `/staff/login`.

#### Scenario: Staff signs out
- **WHEN** a staff member activates "Sign out"
- **THEN** the auth token is cleared and the system navigates to `/staff/login`

### Requirement: Visit requests are grouped into five status columns with live counts
The system SHALL group visit requests into five columns, in this order: Requested, Approved, Checked-in, Checked-out, Denied. Each column SHALL show a count badge equal to the total number of visit requests in that status that match the active search and filters, as reported by the server. The count SHALL NOT be limited to the number of cards currently loaded in the column.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully
- **THEN** each request appears under the column matching its status, and each column's count badge shows the server's total for that status

#### Scenario: Count reflects the full total, not the loaded cards
- **WHEN** 250 visit requests are in the Requested status and only the first 20 have been loaded into the Requested column
- **THEN** the Requested column's count badge shows 250

#### Scenario: Checked-out visitors stay visible on the board
- **WHEN** a visitor on one of the staff member's visit requests checks out
- **THEN** after the next refresh or poll, that request appears in the Checked-out column instead of disappearing from the board, and the Checked-in and Checked-out counts reflect the move

### Requirement: Visit request cards display identifying details
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the assigned host's name, and the scheduled visit date and time. The scheduled time is the request's current preferred visit date/time, distinct from the timestamp the request was submitted. The visitor's name and REQ ID SHALL appear beside the avatar. Purpose of visit and host SHALL share a single line that truncates with an ellipsis rather than wrapping, with the full text available on hover. The scheduled date/time SHALL appear directly beneath that line, above any card-face buttons.

#### Scenario: Card renders request details
- **WHEN** a visit request is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, host name, and the scheduled visit date/time

#### Scenario: Long host label does not wrap
- **WHEN** a card's purpose and host together are wider than the card
- **THEN** the purpose/host line stays on one line, ends in an ellipsis, and shows the full text on hover

#### Scenario: Scheduled time updates after a reschedule
- **WHEN** a visit request's preferred visit date/time has been changed by a reschedule action
- **THEN** the card shows the updated scheduled visit date/time after the board next refreshes

### Requirement: Empty status columns show an empty-state message
The system SHALL, when a status column has no visit requests, show an empty-state message in place of any cards.

#### Scenario: Column has no requests
- **WHEN** a status column has zero visit requests
- **THEN** the system shows an empty-state message instead of any cards

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

### Requirement: Refresh reloads the visit-requests list
The system SHALL present exactly one refresh control on the dashboard. When that control is activated, the system SHALL re-fetch, for every column, the pages that column has already loaded, and re-render the board with the latest data. A column the staff member has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Only one refresh control is shown
- **WHEN** the dashboard finishes loading
- **THEN** exactly one refresh control is visible on the page

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates the refresh control
- **THEN** the system re-fetches every column's loaded pages and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** a staff member has loaded 60 cards into the Requested column, scrolled down, and activates the refresh control
- **THEN** the Requested column still holds up to 60 cards after the refresh and is not scrolled back to the top

### Requirement: Board refreshes automatically in the background
The system SHALL periodically re-fetch, on a fixed interval, the pages each column has already loaded, without requiring staff to activate the refresh control, and SHALL update the board with the result without showing the full-board loading state or resetting any column's scroll position. A request whose status changed SHALL move from its old column to its new one. The system SHALL NOT trigger an automatic refresh while a deny, reschedule, or delegate action is in progress or its dialog is open.

#### Scenario: Board updates without manual refresh
- **WHEN** the automatic refresh interval elapses while the dashboard is open
- **THEN** the system re-fetches each column's loaded pages and updates the board with the result, without showing the full-board loading state

#### Scenario: A request that changed status moves columns
- **WHEN** a request loaded in the Requested column is approved by someone else and the automatic refresh interval elapses
- **THEN** that request no longer appears in the Requested column, appears in the Approved column, and both columns' counts update

#### Scenario: Automatic refresh is suppressed during an in-progress action
- **WHEN** the automatic refresh interval elapses while a deny, reschedule, or delegate dialog is open
- **THEN** the system does not re-fetch the visit-requests list until that dialog is closed

### Requirement: List load failure is reported without crashing
The system SHALL, when the visit-requests list fails to load, show an error message on the dashboard and allow retrying without reloading the page.

#### Scenario: Initial load fails
- **WHEN** the visit-requests list fails to load
- **THEN** the system shows an error message and lets the staff member retry

### Requirement: Dashboard load failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when the visit-requests list fails to load or a refresh fails.

#### Scenario: Initial load fails
- **WHEN** the visit-requests list fails to load
- **THEN** the system shows an error message on the dashboard and also triggers an error notification

#### Scenario: Refresh fails
- **WHEN** a staff member activates a refresh action and the re-fetch fails
- **THEN** the system triggers an error notification and the previously loaded board remains visible

### Requirement: An in-progress approval step shows its pending approver by name
The system SHALL, when a card's invitation has a current approval step, show on the card a badge reading "Level X/Y" together with the name of who the step is pending on. That name is the role's name when the step is assigned to a role, or that person's full name when it is assigned to a specific host user. When the current step is stepOrder 0 (Reception) and the workflow has more than one total step, the system SHALL instead show the *next* step's (stepOrder 1) required role as the pending approver.

#### Scenario: Step pending on a role
- **WHEN** a card's current approval step is assigned to a role, and that step is not Reception's (stepOrder 0) step in a multi-step workflow
- **THEN** the card's badge shows that role's name as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** a card's current approval step is assigned to a specific user (the invitation's host)
- **THEN** the card's badge shows that user's full name as the pending approver

#### Scenario: Reception's step previews the next level instead of naming itself
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the card's badge shows the next step's required role as the pending approver, instead of naming Reception's own step

#### Scenario: Single-step Reception-only workflow is unaffected
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has only one total step
- **THEN** the card's badge shows Reception's own step as the pending approver, unchanged

### Requirement: Dropping a requested card on Approved approves it, using the step endpoint when a workflow is active
The system SHALL, when a card is dropped on the Approved column, approve that invitation: if it has a current approval step, approve that specific step; otherwise approve the invitation directly. On success it SHALL refresh the board and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message. A card whose current approval step is stepOrder 0 (Reception) in a workflow with more than one total step SHALL NOT be draggable to the Approved column at all — "Approve & Delegate" is the only way to advance it.

#### Scenario: Approving a non-workflow invitation
- **WHEN** a card for an invitation with no configured approval workflow is dropped on Approved
- **THEN** the system approves the invitation directly, refreshes the board, and triggers a success notification

#### Scenario: Approving a workflow-backed invitation's current step
- **WHEN** a card for an invitation with a current approval step, other than a Reception step with a further step following, is dropped on Approved
- **THEN** the system approves that specific step, refreshes the board, and triggers a success notification

#### Scenario: Approval rejected by the backend
- **WHEN** an approve attempt (direct or step-based) fails
- **THEN** the system triggers an error notification containing the backend's error message and the board is not otherwise changed

#### Scenario: A Reception-step, multi-step card cannot be drag-approved
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the card cannot be dragged to the Approved column, and only "Approve & Delegate" is available to advance it

### Requirement: Reception's step offers a combined Approve & Delegate action when a further step follows
The system SHALL, on a card whose current approval step is stepOrder 0 (Reception) and whose workflow has more than one total step, present an "Approve & Delegate" action instead of a plain "Delegate" action. Activating it SHALL show a dropdown of employees eligible for the *next* step's (stepOrder 1) required role. Confirming with a selected employee SHALL approve the Reception step and then assign that employee as the approver of the resulting next step, in a single user-facing action; on success it SHALL refresh the board and trigger a success notification naming the newly-assigned approver.

#### Scenario: Reception approves and assigns the next approver together
- **WHEN** a Reception user activates "Approve & Delegate" on a card with a further step, selects an eligible employee, and confirms
- **THEN** the system approves the Reception step, assigns the selected employee as the next step's approver, refreshes the board, and triggers a success notification

#### Scenario: Approve succeeds but assigning the next approver fails
- **WHEN** the approve call in a confirmed "Approve & Delegate" action succeeds but the subsequent assignment call fails
- **THEN** the system triggers an error notification stating the request was approved but the next approver could not be assigned, and refreshes the board so the current (now-advanced) state is visible

#### Scenario: No eligible employees for the next step
- **WHEN** a Reception user activates "Approve & Delegate" and no employees are eligible for the next step's role
- **THEN** the system shows an empty-state message in the dropdown and the confirm action stays disabled

### Requirement: A single-step Reception-only workflow keeps plain approval
The system SHALL NOT present any delegate-style action on a card whose current approval step is stepOrder 0 (Reception) when the workflow has only one total step; approving remains the only action available for that step.

#### Scenario: Reception-only workflow shows no delegate action
- **WHEN** a card's current approval step is stepOrder 0 and the workflow's total step count is 1
- **THEN** neither "Delegate" nor "Approve & Delegate" is shown on that card

### Requirement: Dropping a card on Denied requires a reason and then rejects it
The system SHALL, when a card is dropped on the Denied column, show a dialog requiring a non-empty reason (up to 500 characters) before the deny action can be confirmed. On confirmation it SHALL reject that invitation's current approval step if one exists, or deny the invitation directly otherwise; on success it SHALL close the dialog, refresh the board, and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message and keep the dialog open.

#### Scenario: Deny dialog requires a reason
- **WHEN** a staff member drops a card on Denied and leaves the reason field empty
- **THEN** the deny confirmation action stays disabled

#### Scenario: Deny cancelled
- **WHEN** a staff member cancels the deny dialog
- **THEN** the dialog closes and the invitation is not changed

#### Scenario: Denying a non-workflow invitation
- **WHEN** a staff member confirms a deny with a reason for an invitation with no configured approval workflow
- **THEN** the system denies the invitation directly, closes the dialog, refreshes the board, and triggers a success notification

#### Scenario: Rejecting a workflow-backed invitation's current step
- **WHEN** a staff member confirms a deny with a reason for an invitation with a current approval step
- **THEN** the system rejects that specific step, closes the dialog, refreshes the board, and triggers a success notification

#### Scenario: Deny rejected by the backend
- **WHEN** a deny/reject attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the dialog remains open

### Requirement: Visitor Info Modal Details Stack in One Column on Narrow Screens
Below the `sm` breakpoint, each detail section of the Visitor Info modal
SHALL list its label/value pairs one per row, at the full width of the
section. That covers visit details, contact details, vehicles and
additional notes. A full-width entry (such as notes) SHALL NOT cause the
other entries to pack side by side. From `sm` upward, the two-column
layout SHALL be unchanged.

#### Scenario: Visitor Info modal on a phone
- **WHEN** a staff user opens a visit's Visitor Info modal at 375px wide
- **THEN** each detail label and its value render at the section's full
  width, one entry per row, and the notes entry spans the section

### Requirement: Status column headers stay visible while cards scroll
The system SHALL keep each status column's header (label and count badge) visible at all times while the staff member scrolls through that column's cards, so the status of every card on screen is always identifiable. At `lg` and wider, each column's cards SHALL scroll within that column. The page header, search field, and filters SHALL also stay in place.

#### Scenario: Scrolling a long column on desktop
- **WHEN** a staff member scrolls down through 40 cards in the Requested column at 1280px wide
- **THEN** the "Requested" header and its count stay visible at the top of that column, and the other columns' headers stay visible too

#### Scenario: Columns scroll independently
- **WHEN** a staff member scrolls the Requested column down at 1280px wide
- **THEN** the Approved, Checked-in, and Denied columns keep their own scroll position

### Requirement: Columns load visit requests lazily in pages
The system SHALL load each status column's visit requests from the server in pages of 20, starting with the first page when the board opens. When the staff member scrolls near the end of a column's loaded cards and more exist on the server, the system SHALL load that column's next page and append it, without a full-board loading state and without reloading other columns. The system SHALL show a loading indicator at the end of the column while a page loads. When every request in the column is loaded, it SHALL NOT request further pages. A card SHALL NOT appear twice in the same column, even if new requests arrive between page loads.

#### Scenario: First page on open
- **WHEN** the dashboard opens and the Requested status has 250 visit requests
- **THEN** the Requested column shows the 20 most recent and its count badge shows 250

#### Scenario: Scrolling loads the next page
- **WHEN** a staff member scrolls to the end of the 20 cards loaded in the Requested column
- **THEN** a loading indicator appears at the end of that column, and the next 20 requests are appended beneath the existing cards

#### Scenario: Column fully loaded
- **WHEN** every visit request in a column has been loaded and the staff member scrolls to its end
- **THEN** no further page is requested for that column

#### Scenario: No duplicates when new requests arrive mid-scroll
- **WHEN** a new visit request is submitted after the first page of a column loaded and the staff member then scrolls to load the next page
- **THEN** no card appears twice in that column

#### Scenario: A page load fails
- **WHEN** loading a column's next page fails
- **THEN** the already-loaded cards stay visible, and the end of the column shows a retry control that loads that page again when activated

### Requirement: Checked-out cards are read-only
The system SHALL let a card in the Checked-out column open Visitor Info, by activating the card or its Visitor info icon button, and SHALL offer no other action on it. It SHALL NOT offer approve, deny, reschedule, delegate, or edit, and SHALL show no labelled card-face buttons. A Checked-out card SHALL NOT be draggable, and the Checked-out column SHALL NOT accept dropped cards. This applies equally to the admin Invitations board, which uses the same board component.

#### Scenario: Checked-out card actions
- **WHEN** a staff member views a card in the Checked-out column
- **THEN** the card shows no labelled card-face buttons, and its icon row shows only Visitor info

#### Scenario: Visitor Info on a checked-out card
- **WHEN** a staff member activates a Checked-out card or its Visitor info icon button
- **THEN** the Visitor Info modal opens for that visit and shows its status as "Checked Out"

#### Scenario: Cannot drop onto the Checked-out column
- **WHEN** a staff member drags a Requested card over the Checked-out column and releases it
- **THEN** the card stays in the Requested column and no status change is sent to the server

### Requirement: Checked-out column empty state
The system SHALL show the message "No checked-out visits" when the Checked-out column has no visit requests that match the active search and filters.

#### Scenario: No checked-out visits
- **WHEN** the Checked-out column has zero visit requests
- **THEN** it shows "No checked-out visits" instead of any cards

### Requirement: Checked-in cards offer a confirmed manual check-out to Admin and Reception
The system SHALL show a "Check Out" action on every card in the Checked-in column when the signed-in staff member holds the Admin or Reception role. It SHALL NOT show this action to staff who hold neither role, and it SHALL NOT show it on cards in any other column. Activating the action SHALL open a confirmation dialog that names the visitor and the tracking ID. The visit SHALL be checked out only after the staff member confirms. On confirmation the system SHALL send one check-out request for that visit, carrying a single idempotency key for that confirmation.

#### Scenario: Reception sees Check Out on a checked-in card
- **WHEN** a staff member with the Reception role views a card in the Checked-in column
- **THEN** the card shows both "Visitor Info" and "Check Out" actions

#### Scenario: Host does not see Check Out
- **WHEN** a staff member with only the Host role views a card in the Checked-in column
- **THEN** the card shows "Visitor Info" and no "Check Out" action

#### Scenario: Check Out is limited to the Checked-in column
- **WHEN** a Reception or Admin staff member views cards in the Requested, Approved, Checked-out, or Denied columns
- **THEN** none of those cards shows a "Check Out" action

#### Scenario: Cancelling the confirmation changes nothing
- **WHEN** a staff member activates "Check Out" on a checked-in card and then cancels the confirmation dialog
- **THEN** the dialog closes, no check-out request is sent, and the card stays in the Checked-in column

#### Scenario: Confirming checks the visitor out
- **WHEN** a staff member confirms the check-out of a checked-in visitor and the server accepts it
- **THEN** the dialog closes, a success notification names the visitor as checked out, and after the board reloads the card appears in the Checked-out column with the Checked-in and Checked-out counts updated

#### Scenario: Confirm cannot be submitted twice
- **WHEN** a staff member confirms a check-out and the request is still in flight
- **THEN** the confirm button is disabled and reads "Checking out…", and activating it again sends no second request

#### Scenario: The visitor already left by QR scan
- **WHEN** a staff member confirms a check-out but the server reports the visit is no longer checked in
- **THEN** an error notification shows the server's message, the dialog closes, and the board reloads so the card shows its current column

#### Scenario: The server rejects the check-out
- **WHEN** a staff member confirms a check-out and the server rejects it for any other reason (for example, missing permission or a network failure)
- **THEN** an error notification shows the failure message, and the card stays in the Checked-in column

#### Scenario: Background refresh does not interrupt a check-out
- **WHEN** the check-out confirmation dialog is open or its request is in flight and the background refresh interval elapses
- **THEN** the board skips that refresh, so the dialog and card are not disrupted

### Requirement: Activating a card opens its Visitor Info
The system SHALL open the Visitor Info modal for a visit request when a staff member activates the card's body by mouse click, tap, or keyboard (Enter or Space while the card has focus). Activating any button or icon button on the card SHALL perform only that control's action and SHALL NOT also open Visitor Info. When the dashboard loads with an `invitationId` query parameter naming a visit request, the system SHALL open that visit's Visitor Info modal once.

#### Scenario: Clicking a card opens Visitor Info
- **WHEN** a staff member clicks a card anywhere outside its buttons
- **THEN** the Visitor Info modal opens for that visit request

#### Scenario: Keyboard activation
- **WHEN** a card has keyboard focus and the staff member presses Enter or Space
- **THEN** the Visitor Info modal opens for that visit request

#### Scenario: Card buttons do not also open Visitor Info
- **WHEN** a staff member activates the Approve, Deny, or Check Out button, or any icon button, on a card
- **THEN** only that control's action runs, and the Visitor Info modal does not open

#### Scenario: Deep link opens Visitor Info
- **WHEN** the dashboard is opened with `?invitationId=<id>` (for example, from a clicked push notification)
- **THEN** the Visitor Info modal for that visit request opens once the page loads

### Requirement: Cards show only their deciding actions as buttons
The system SHALL render as card-face buttons only the actions that decide a request's next state. An actionable Requested card SHALL show "Approve" and "Deny" side by side in one row. When Reception's step is current, it SHALL show "Approve & Delegate" (if a further step follows) or "Approve" (if Reception is the only step), with "Deny" beside it. A Checked-in card SHALL show "Check Out" only to staff holding the Admin or Reception role. Approved, Checked-out, and Denied cards, and Requested cards that are not yet actionable, SHALL show no card-face buttons. Visitor Info, Reschedule, Edit, and Delegate SHALL NOT appear as labelled card-face buttons; they are icon buttons (see "Secondary card actions are icon buttons").

#### Scenario: Requested card actions
- **WHEN** a staff member views an actionable Requested card that is not on Reception's step
- **THEN** the card shows "Approve" and "Deny" buttons on one row and no other card-face buttons

#### Scenario: Reception step with a further step
- **WHEN** a Reception user views a Requested card whose current step is Reception's and whose workflow has more than one step
- **THEN** the card shows "Approve & Delegate" and "Deny" buttons on one row

#### Scenario: Approved card has no card-face buttons
- **WHEN** a staff member views a card in the Approved column
- **THEN** the card shows no labelled card-face buttons, only its icon row

### Requirement: Secondary card actions are icon buttons
The system SHALL show the secondary actions as a row of compact icon buttons along the bottom of each card, separate from the labelled card-face buttons. The row SHALL contain, in this order and only when eligible:
- "Visitor info" (always)
- "Reschedule" (status `submitted` or `approved`)
- "Edit" (status `submitted` or `approved`)
- "Delegate" (a current approval step exists that is not Reception's own step)

Each icon button SHALL have an accessible name of "<action> for <REQ ID>" and SHALL show the action's name as a tooltip on hover and keyboard focus. Activating one SHALL perform the same action as the button it replaces. Below `lg`, each icon button SHALL have a tap target of at least 40×40 CSS pixels.

#### Scenario: Requested card icons
- **WHEN** a staff member views a Requested card whose status is `submitted` and that has a current approval step not on Reception's step
- **THEN** the icon row shows Visitor info, Reschedule, Edit, and Delegate, in that order

#### Scenario: Approved card icons
- **WHEN** a staff member views an Approved card with no current approval step
- **THEN** the icon row shows Visitor info, Reschedule, and Edit, in that order

#### Scenario: Denied card icons
- **WHEN** a staff member views a Denied card
- **THEN** the icon row shows only Visitor info

#### Scenario: Icon names are discoverable
- **WHEN** a staff member hovers over or tabs to an icon button
- **THEN** a tooltip shows that action's name, and assistive technology announces "<action> for <REQ ID>"

### Requirement: A card offers a Reschedule icon button for requests that are still submitted or approved
The system SHALL show a "Reschedule" icon button on any visit request card whose status is `submitted` or `approved`. Activating it SHALL open a modal dialog requiring both a new date and a new time before its save action is enabled. On save it SHALL update the invitation's preferred visit date/time, close the modal, refresh the board, and trigger a success notification. On failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Reschedule item only for eligible statuses
- **WHEN** a visit request's status is not `submitted` or `approved`
- **THEN** its card does not show a Reschedule icon button

#### Scenario: Reschedule modal opens from the icon
- **WHEN** a staff member activates the Reschedule icon button on an eligible card
- **THEN** the system opens a modal dialog with empty date and time fields

#### Scenario: Save disabled until both fields are filled
- **WHEN** the reschedule modal's date or time field is empty
- **THEN** the save action is disabled

#### Scenario: Reschedule succeeds
- **WHEN** a staff member fills both fields in the reschedule modal and activates save
- **THEN** the system updates the invitation's preferred date/time, closes the modal, refreshes the board, and triggers a success notification

#### Scenario: Reschedule fails
- **WHEN** a reschedule save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

### Requirement: A card offers a Delegate icon button for requests with a current approval step
The system SHALL show a "Delegate" icon button on any visit request card whose invitation has a current approval step that is not Reception's own step. Activating it SHALL open a modal dialog. The modal SHALL offer a host picker scoped to the step's configured approver role, or all hosts when the step is not role-scoped, and SHALL require a selection before its confirm action is enabled. On confirmation it SHALL reassign the current approval step to the selected host, close the modal, refresh the board, and trigger a success notification naming the delegate. On failure it SHALL keep the modal open and trigger an error notification showing the backend's message.

#### Scenario: Delegate item only when a step is pending
- **WHEN** a visit request's invitation has no current approval step
- **THEN** its card does not show a Delegate icon button

#### Scenario: Delegate modal opens from the icon
- **WHEN** a staff member activates the Delegate icon button on an eligible card
- **THEN** the system opens a modal dialog with a host picker

#### Scenario: Host picker scoped to the step's role
- **WHEN** the current approval step is assigned to a specific role
- **THEN** the delegate modal's host picker offers only hosts holding that role

#### Scenario: Confirm disabled until a host is selected
- **WHEN** no host is selected in the delegate modal
- **THEN** the confirm action is disabled

#### Scenario: Delegate succeeds
- **WHEN** a staff member selects a host in the delegate modal and activates confirm
- **THEN** the system reassigns the current approval step to that host, closes the modal, refreshes the board, and triggers a success notification naming the delegate

#### Scenario: Delegate fails
- **WHEN** a delegate confirmation attempt fails
- **THEN** the system triggers an error notification containing the backend's error message and the modal remains open

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

### Requirement: Reception can export invitations from the staff dashboard
The staff dashboard SHALL show an "Export" button at the right of its
"Invitations" title row, as the admin Invitations page does, but only to a
signed-in user who holds the Reception role. It
SHALL NOT be shown to any other staff member, such as a host. Activating
it SHALL open the same Export invitations dialog the admin-invitations
capability specifies, with the same prefill, validation, download, and
error behaviour. The dialog's Status SHALL open on the board's current
Status filter ("All statuses" when none is set). The export SHALL be
limited to the invitations this board shows the user (`relevantToMe`),
combined with the board's search, purpose of visit, registration type and
source filters.

#### Scenario: Reception sees and uses Export
- **WHEN** a Reception user opens the staff dashboard, activates "Export",
  sets Status "Approved", and confirms with Format CSV
- **THEN** the browser downloads `invitations-approved-<today>.csv` limited
  to the invitations that user's board shows, filtered to approved ones

#### Scenario: A host does not see Export
- **WHEN** a staff member without the Reception role (for example a host)
  opens the staff dashboard
- **THEN** no "Export" button is shown

#### Scenario: Dialog opens on the board's status
- **WHEN** a Reception user with no Status filter set opens the Export
  invitations dialog from the staff dashboard
- **THEN** the dialog's Status shows "All statuses" and the hint says the
  date range applies to the created date. With a Status filter set, the
  dialog opens on that status instead

#### Scenario: Export button at tablet and laptop widths
- **WHEN** a Reception user views the staff dashboard at any width from
  360px to 1920px
- **THEN** the Export button is fully visible in the title row with its
  "Export" label, and the page has no horizontal scroll

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
