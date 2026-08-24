# staff-login Specification

## Purpose

The staff-login capability gives staff a dedicated, branded sign-in gateway into the system via SSO, distinct from the visitor-facing flows, and a placeholder landing area once signed in.

## Requirements

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

### Requirement: Staff signs in with an email and password form
The system SHALL present an email field, a password field, and a single primary submit action ("Sign In") on the login screen, and SHALL NOT present an SSO-redirect action.
Submitting the form with both fields filled SHALL send a login request with the entered email and password to the backend and, on success, store the returned auth token and navigate to `/staff/dashboard`.

#### Scenario: Staff submits valid credentials
- **WHEN** a staff member enters an email and password and submits the form
- **THEN** the system sends a login request with those credentials and, once an auth token is returned, stores the token and navigates to `/staff/dashboard`

#### Scenario: Staff submits the form with a missing field
- **WHEN** a staff member submits the form with the email or password field empty
- **THEN** the system does not send a login request and shows a validation message indicating the missing field

### Requirement: Login failure is reported without a stuck loading state
The system SHALL show an inline error message on the login screen if the login request fails (invalid credentials, network error, or non-success response), and SHALL return the "Sign In" action to an activatable state so the staff member can retry.

#### Scenario: Login request fails
- **WHEN** the login request fails because of invalid credentials, a network error, or a non-success response
- **THEN** the system shows an inline error message on the login screen and re-enables the "Sign In" action

### Requirement: Login failure also triggers a notification
The system SHALL, in addition to the inline error message, trigger an error notification when the login request fails.

#### Scenario: Login request fails
- **WHEN** the login request fails
- **THEN** the system shows an inline error message on the login screen and also triggers an error notification

### Requirement: Successful sign-in lands on the staff dashboard
The system SHALL render the full staff dashboard (the `staff-dashboard` capability) at the `/staff/dashboard` route as the landing target after a successful sign-in.

#### Scenario: Staff reaches the dashboard
- **WHEN** a user navigates to `/staff/dashboard` with a valid session
- **THEN** the system renders the staff dashboard: sidebar, workspace header, and visit-requests kanban board

### Requirement: An expired or unauthorized session redirects to the login screen
The system SHALL redirect the browser to `/admin/login` whenever a staff or admin page detects a missing, expired, or unauthorized session.

#### Scenario: Session guard redirects on an admin or staff page
- **WHEN** a staff or admin page loads without a valid session, or a request fails with an unauthorized response
- **THEN** the system redirects the browser to `/admin/login`
