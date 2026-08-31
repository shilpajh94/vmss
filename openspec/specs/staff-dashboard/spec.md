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
The system SHALL render, for an authenticated session, a sidebar (brand mark, "All visitors" / "My actions" / "Audit trail" navigation with "All visitors" selected, and a "Help & Support" link) and a main workspace containing the header, search bar, and visit-requests kanban board.

#### Scenario: Authenticated staff views the dashboard
- **WHEN** an authenticated staff member's dashboard finishes loading
- **THEN** the sidebar, the "Visits" workspace header, the search bar, and the kanban board are all visible

### Requirement: Other sidebar navigation items are visible but not yet functional
The system SHALL render the "Help & Support" link per the design, but SHALL NOT navigate anywhere when it is activated.

#### Scenario: Inert nav item activated
- **WHEN** a staff member activates "Help & Support"
- **THEN** the current view does not change

### Requirement: "Audit trail" opens the Audit Trail page
The system SHALL, when a staff member activates "Audit trail" in the sidebar, navigate to the Audit Trail page.

#### Scenario: Staff opens Audit trail
- **WHEN** an authenticated staff member activates "Audit trail" in the sidebar
- **THEN** the system navigates to the Audit Trail page

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

### Requirement: Visit requests are grouped into four status columns with live counts
The system SHALL group visit requests into four columns — Requested, Approved, Checked-in, Denied — each showing a count badge equal to the number of requests currently in that column.

#### Scenario: Requests load successfully
- **WHEN** the visit-requests list loads successfully
- **THEN** each request appears under the column matching its status, and each column's count badge reflects the number of requests shown in it

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
The system SHALL, as the staff member types in the search field, show only visit requests whose visitor name, host name, or REQ ID contains the entered text (case-insensitive), across all columns.

#### Scenario: Search narrows the board
- **WHEN** a staff member enters text in the search field
- **THEN** only visit requests whose visitor name, host name, or REQ ID contains that text remain visible, in their existing columns

#### Scenario: Search is cleared
- **WHEN** a staff member clears the search field
- **THEN** all loaded visit requests are shown again

### Requirement: Filters affordance is presented but not yet functional
The system SHALL display the "Filters" control per the design, but SHALL NOT apply any filtering when it is activated.

#### Scenario: Filters activated
- **WHEN** a staff member activates "Filters"
- **THEN** the visible visit requests do not change

### Requirement: Refresh reloads the visit-requests list
The system SHALL, when a refresh action is activated, re-fetch the visit-requests list from the backend and re-render the board with the latest data.

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates a refresh action
- **THEN** the system re-fetches the visit-requests list and updates the board with the result

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
The system SHALL, when an expanded card's invitation has a current approval step, show "Step X of Y" together with the name of who it is pending on: the role's name when the step is assigned to a role, or that person's full name when it is assigned to a specific host user.

#### Scenario: Step pending on a role
- **WHEN** an expanded card's current approval step is assigned to a role
- **THEN** the system shows that role's name as the pending approver

#### Scenario: Step pending on a specific host
- **WHEN** an expanded card's current approval step is assigned to a specific user (the invitation's host)
- **THEN** the system shows that user's full name as the pending approver

### Requirement: Dropping a requested card on Approved approves it, using the step endpoint when a workflow is active
The system SHALL, when a card is dropped on the Approved column, approve that invitation: if it has a current approval step, approve that specific step; otherwise approve the invitation directly. On success it SHALL refresh the board and trigger a success notification; on failure it SHALL trigger an error notification showing the backend's message.

#### Scenario: Approving a non-workflow invitation
- **WHEN** a card for an invitation with no configured approval workflow is dropped on Approved
- **THEN** the system approves the invitation directly, refreshes the board, and triggers a success notification

#### Scenario: Approving a workflow-backed invitation's current step
- **WHEN** a card for an invitation with a current approval step is dropped on Approved
- **THEN** the system approves that specific step, refreshes the board, and triggers a success notification

#### Scenario: Approval rejected by the backend
- **WHEN** an approve attempt (direct or step-based) fails
- **THEN** the system triggers an error notification containing the backend's error message and the board is not otherwise changed

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
