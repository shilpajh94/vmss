## MODIFIED Requirements

### Requirement: An expired or unauthorized session redirects to the login screen
The system SHALL redirect the browser to `/staff/login` whenever a staff-only page detects a missing, expired, or unauthorized session, and to `/admin/login` whenever an admin-only page detects a missing, expired, or unauthorized session.

#### Scenario: Session guard redirects on an admin or staff page
- **WHEN** an admin-only page loads without a valid session, or a request from that page fails with an unauthorized response
- **THEN** the system redirects the browser to `/admin/login`

#### Scenario: Session guard redirects on a staff-only page
- **WHEN** a staff-only page (staff dashboard, staff audit trail, staff visitor registration) loads without a valid session, or a request from that page fails with an unauthorized response
- **THEN** the system redirects the browser to `/staff/login`
