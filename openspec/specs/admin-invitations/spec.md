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

### Requirement: Invitations are grouped into four status columns with live counts
The system SHALL group invitations into four columns — Requested, Approved, Checked-in, Denied — each showing a count badge equal to the number of invitations currently in that column, using the same board component as the staff dashboard.

#### Scenario: Invitations load successfully
- **WHEN** the invitations list loads successfully
- **THEN** each invitation appears under the column matching its status, and each column's count badge reflects the number shown in it

#### Scenario: Empty column
- **WHEN** a status column has zero invitations
- **THEN** the system shows an empty-state message instead of any cards

### Requirement: Search filters visible invitations by visitor name or tracking ID
The system SHALL, as the admin types in the search field, show only invitations whose visitor name or tracking ID contains the entered text (case-insensitive), across all columns.

#### Scenario: Search narrows the board
- **WHEN** an admin enters text in the search field
- **THEN** only invitations whose visitor name or tracking ID contains that text remain visible, in their existing columns

### Requirement: Refresh reloads the invitations list
The system SHALL, when the refresh action is activated, re-fetch the invitations list, the role list, and the employee directory, and re-render the board with the latest data.

#### Scenario: Admin refreshes the board
- **WHEN** an admin activates the refresh action
- **THEN** the system re-fetches the underlying data and updates the board with the result

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
