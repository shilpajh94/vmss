# staff-login Specification

## Purpose

The staff-login capability gives staff a dedicated, branded sign-in gateway into the system via SSO, distinct from the visitor-facing flows, and a placeholder landing area once signed in.

## Requirements

### Requirement: Staff login screen is reachable at a dedicated route
The system SHALL render the staff Enterprise Sign In screen at the `/staff/login` route, matching the approved "staff-sso-login" design: a Staff Gateway header, a centered sign-in card, and a footer with legal links.

#### Scenario: Staff navigates to the login route
- **WHEN** a user navigates to `/staff/login`
- **THEN** the system renders the Staff Gateway header, the "Enterprise Sign In" card with a "Sign in with SSO" action, and the footer

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL render the staff login screen with its own dark-themed header ("VisitorPass" brand mark plus a "Staff Gateway" badge and system-status indicator) instead of the visitor portal's header, and SHALL NOT reuse the visitor portal's light header component.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the staff login screen renders
- **THEN** the visitor portal's light header is not present, and the dark Staff Gateway header is shown instead

### Requirement: Staff initiates sign-in via a single SSO action
The system SHALL present exactly one primary action, "Sign in with SSO", on the login screen, and SHALL NOT present username/password fields.
Activating the action SHALL request SSO initiation from the backend and, on success, navigate the browser to the returned redirect URL.

#### Scenario: Staff activates the SSO action
- **WHEN** a staff member activates "Sign in with SSO"
- **THEN** the system requests SSO initiation and, once a redirect URL is returned, navigates to it

### Requirement: SSO initiation failure is reported without a stuck loading state
The system SHALL show an inline error message on the login screen if SSO initiation fails, and SHALL return the "Sign in with SSO" action to an activatable state so the staff member can retry.

#### Scenario: Initiation request fails
- **WHEN** the SSO initiation request fails (network error or non-success response)
- **THEN** the system shows an inline error message on the login screen and re-enables the "Sign in with SSO" action

### Requirement: Successful SSO sign-in lands on the staff dashboard placeholder
The system SHALL render a placeholder staff dashboard at the `/staff/dashboard` route as the landing target after a successful SSO sign-in.

#### Scenario: Staff reaches the dashboard placeholder
- **WHEN** a user navigates to `/staff/dashboard`
- **THEN** the system renders the placeholder staff dashboard page
