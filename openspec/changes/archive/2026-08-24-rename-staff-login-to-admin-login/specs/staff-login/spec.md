## MODIFIED Requirements

### Requirement: Staff login screen is reachable at a dedicated route
The system SHALL render the staff Enterprise Sign In screen at the `/admin/login` route, matching the approved "staff-sso-login" design: an Admin Gateway header, a centered sign-in card, and a footer with legal links.

#### Scenario: Staff navigates to the login route
- **WHEN** a user navigates to `/admin/login`
- **THEN** the system renders the Admin Gateway header, the "Enterprise Sign In" card with a sign-in action, and the footer

#### Scenario: The old route no longer serves the login screen
- **WHEN** a user navigates to `/staff/login`
- **THEN** the system does not render the Enterprise Sign In screen at that path

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL render the staff login screen with its own dark-themed header ("VisitorPass" brand mark plus an "Admin Gateway" badge and system-status indicator) instead of the visitor portal's header, and SHALL NOT reuse the visitor portal's light header component.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the staff login screen renders
- **THEN** the visitor portal's light header is not present, and the dark Admin Gateway header is shown instead

## ADDED Requirements

### Requirement: An expired or unauthorized session redirects to the login screen
The system SHALL redirect the browser to `/admin/login` whenever a staff or admin page detects a missing, expired, or unauthorized session.

#### Scenario: Session guard redirects on an admin or staff page
- **WHEN** a staff or admin page loads without a valid session, or a request fails with an unauthorized response
- **THEN** the system redirects the browser to `/admin/login`
