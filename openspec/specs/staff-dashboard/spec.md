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
The system SHALL render, for each visit request, an avatar showing the visitor's initials, the REQ ID, the visitor's name, the assigned host's name, and the scheduled date and time.

#### Scenario: Card renders request details
- **WHEN** a visit request is displayed on the board
- **THEN** its card shows the visitor's initials, REQ ID, name, host name, and scheduled date/time

### Requirement: Empty status columns show an empty-state message
The system SHALL, when a status column has no visit requests, show an empty-state message in place of any cards.

#### Scenario: Column has no requests
- **WHEN** a status column has zero visit requests
- **THEN** the system shows an empty-state message instead of any cards

### Requirement: Search filters visible requests by visitor, host, or REQ ID
The system SHALL, as the staff member types in the search field, show only visit requests whose visitor name or REQ ID contains the entered text (case-insensitive), across all columns. The search SHALL be applied by the server to every column's results, so matches beyond the cards already loaded are found, and each column's count badge SHALL reflect the searched total.

#### Scenario: Search narrows the board
- **WHEN** a staff member enters text in the search field
- **THEN** only visit requests whose visitor name or REQ ID contains that text are shown, in their existing columns, and each column's count shows how many matches exist in that status

#### Scenario: Search finds a request that was not loaded yet
- **WHEN** a staff member searches for the REQ ID of a request that is older than every card loaded in its column
- **THEN** that request appears in its column

#### Scenario: Search is cleared
- **WHEN** a staff member clears the search field
- **THEN** each column reloads from its first page with no search applied

### Requirement: Filters narrow the board by purpose of visit and registration type
The system SHALL provide a "Filters" control that lets a staff member select a Purpose of Visit and/or a Registration Type (Individual / Group). When one or both are selected, the system SHALL show only visit requests matching all selected criteria, combined with any active search text, across all columns. The filters SHALL be applied by the server to every column's results, and each column's count badge SHALL reflect the filtered total. Clearing a filter SHALL restore requests that only failed to match that criterion.

#### Scenario: Filtering by purpose of visit
- **WHEN** a staff member selects a Purpose of Visit filter value
- **THEN** only visit requests whose purpose of visit matches that value are shown, in their existing columns

#### Scenario: Filtering by registration type
- **WHEN** a staff member selects a Registration Type filter value
- **THEN** only visit requests whose registration type matches that value are shown, in their existing columns

#### Scenario: Combined with search
- **WHEN** a staff member has both a search term and a filter active
- **THEN** only visit requests matching both the search term and the active filter(s) are shown

#### Scenario: Changing a filter restarts every column from its first page
- **WHEN** a staff member has scrolled a column past its first page and then changes a filter
- **THEN** every column reloads from its first page with the new filter applied

#### Scenario: Filters cleared
- **WHEN** a staff member clears all active filters
- **THEN** all visit requests matching only the current search text (if any) are shown again

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

### Requirement: Activating a card expands it and loads its approval-step progress
The system SHALL, when a visit request card is activated, toggle it between collapsed and expanded; on first expansion it SHALL fetch that invitation's detail and, once loaded, show either its current approval step's progress or a message that it has no multi-step approval workflow. Activating an already-expanded card SHALL collapse it without re-fetching.

#### Scenario: Card expanded for the first time
- **WHEN** a staff member activates a collapsed card
- **THEN** the system expands the card, shows a loading indicator, fetches the invitation's detail, and then shows its step progress or the no-workflow message

#### Scenario: Card re-expanded after detail already loaded
- **WHEN** a staff member collapses and then re-activates a card whose detail was already fetched
- **THEN** the system expands the card immediately using the cached detail without a new fetch

#### Scenario: Detail fetch fails
- **WHEN** an invitation's detail fails to load after expanding its card
- **THEN** the system triggers an error notification and the card does not crash

### Requirement: An in-progress approval step shows its pending approver by name
The system SHALL, when an expanded card's invitation has a current approval step, show "Step X of Y" together with the name of who it is pending on: the role's name when the step is assigned to a role, or that person's full name when it is assigned to a specific host user. When the current step is stepOrder 0 (Reception) and the workflow has more than one total step, the system SHALL instead show the *next* step's (stepOrder 1) required role as the pending approver, both on the collapsed card badge and the expanded detail line.

#### Scenario: Step pending on a role
- **WHEN** an expanded card's current approval step is assigned to a role, and that step is not Reception's (stepOrder 0) step in a multi-step workflow
- **THEN** the system shows that role's name as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** an expanded card's current approval step is assigned to a specific user (the invitation's host)
- **THEN** the system shows that user's full name as the pending approver

#### Scenario: Reception's step previews the next level instead of naming itself
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has more than one total step
- **THEN** the system shows the next step's required role as the pending approver, on both the collapsed badge and the expanded detail line, instead of naming Reception's own step

#### Scenario: Single-step Reception-only workflow is unaffected
- **WHEN** a card's current approval step is stepOrder 0 (Reception) and the workflow has only one total step
- **THEN** the system shows Reception's own step as the pending approver, unchanged

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

### Requirement: An expanded card offers rescheduling for requests that are still submitted or approved
The system SHALL, on an expanded card whose invitation's status is `submitted` or `approved`, show a reschedule form requiring both a new date and a new time before its save action is enabled. On save it SHALL update the invitation's preferred visit date/time, refresh the board, and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message.

#### Scenario: Reschedule form only for eligible statuses
- **WHEN** a card for an invitation whose status is not `submitted` or `approved` is expanded
- **THEN** the system does not show a reschedule form on that card

#### Scenario: Save disabled until both fields are filled
- **WHEN** an expanded, reschedulable card's date or time field is empty
- **THEN** the save action is disabled

#### Scenario: Reschedule succeeds
- **WHEN** a staff member fills both fields and activates save
- **THEN** the system updates the invitation's preferred date/time, refreshes the board, and triggers a success notification

#### Scenario: Reschedule fails
- **WHEN** a reschedule save attempt fails
- **THEN** the system triggers an error notification containing the backend's error message

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
The system SHALL show a card in the Checked-out column with Visitor Info as its only action. It SHALL NOT offer approve, deny, reschedule, delegate, or edit on it. A Checked-out card SHALL NOT be draggable, and the Checked-out column SHALL NOT accept dropped cards. This applies equally to the admin Invitations board, which uses the same board component.

#### Scenario: Checked-out card actions
- **WHEN** a staff member views a card in the Checked-out column
- **THEN** the card shows a "Visitor Info" action and no Approve, Deny, Reschedule, Delegate, or Edit action

#### Scenario: Visitor Info on a checked-out card
- **WHEN** a staff member activates "Visitor Info" on a Checked-out card
- **THEN** the Visitor Info modal opens for that visit and shows its status as "Checked Out"

#### Scenario: Cannot drop onto the Checked-out column
- **WHEN** a staff member drags a Requested card over the Checked-out column and releases it
- **THEN** the card stays in the Requested column and no status change is sent to the server

### Requirement: Checked-out column empty state
The system SHALL show the message "No checked-out visits" when the Checked-out column has no visit requests that match the active search and filters.

#### Scenario: No checked-out visits
- **WHEN** the Checked-out column has zero visit requests
- **THEN** it shows "No checked-out visits" instead of any cards
