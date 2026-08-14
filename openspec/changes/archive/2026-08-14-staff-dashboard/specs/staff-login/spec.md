## MODIFIED Requirements

### Requirement: Successful SSO sign-in lands on the staff dashboard
The system SHALL render the full staff dashboard (the `staff-dashboard` capability) at the `/staff/dashboard` route as the landing target after a successful SSO sign-in.

#### Scenario: Staff reaches the dashboard
- **WHEN** a user navigates to `/staff/dashboard` with a valid session
- **THEN** the system renders the staff dashboard: sidebar, workspace header, and visit-requests kanban board
