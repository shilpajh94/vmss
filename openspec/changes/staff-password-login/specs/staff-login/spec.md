## MODIFIED Requirements

### Requirement: Staff login screen is reachable at a dedicated route
The system SHALL render the staff Enterprise Sign In screen at the `/staff/login` route: a Staff Gateway header, a centered sign-in card with an email/password form, and a footer with legal links.

#### Scenario: Staff navigates to the login route
- **WHEN** a user navigates to `/staff/login`
- **THEN** the system renders the Staff Gateway header, the "Enterprise Sign In" card with email and password fields and a submit action, and the footer

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Staff initiates sign-in via a single SSO action
**Reason**: SSO is replaced by a direct username/password login against `/api/v1/auth/login`.
**Migration**: Use the new "Staff signs in with an email and password form" requirement.

The system SHALL present exactly one primary action, "Sign in with SSO", on the login screen, and SHALL NOT present username/password fields.
Activating the action SHALL request SSO initiation from the backend and, on success, navigate the browser to the returned redirect URL.

#### Scenario: Staff activates the SSO action
- **WHEN** a staff member activates "Sign in with SSO"
- **THEN** the system requests SSO initiation and, once a redirect URL is returned, navigates to it

### Requirement: SSO initiation failure is reported without a stuck loading state
**Reason**: Replaced by password-login failure handling; there is no SSO initiation request anymore.
**Migration**: Use the new "Login failure is reported without a stuck loading state" requirement.

The system SHALL show an inline error message on the login screen if SSO initiation fails, and SHALL return the "Sign in with SSO" action to an activatable state so the staff member can retry.

#### Scenario: Initiation request fails
- **WHEN** the SSO initiation request fails (network error or non-success response)
- **THEN** the system shows an inline error message on the login screen and re-enables the "Sign in with SSO" action

### Requirement: SSO initiation failure also triggers a notification
**Reason**: Replaced by password-login failure handling; there is no SSO initiation request anymore.
**Migration**: Use the new "Login failure also triggers a notification" requirement.

The system SHALL, in addition to the inline error message, trigger an error notification when SSO initiation fails.

#### Scenario: Initiation request fails
- **WHEN** the SSO initiation request fails (network error or non-success response)
- **THEN** the system shows an inline error message on the login screen and also triggers an error notification

### Requirement: Successful SSO sign-in lands on the staff dashboard
**Reason**: Superseded by the generic "Successful sign-in lands on the staff dashboard" requirement, since sign-in is no longer SSO-based.
**Migration**: Use the new "Successful sign-in lands on the staff dashboard" requirement.

The system SHALL render the full staff dashboard (the `staff-dashboard` capability) at the `/staff/dashboard` route as the landing target after a successful SSO sign-in.

#### Scenario: Staff reaches the dashboard
- **WHEN** a user navigates to `/staff/dashboard` with a valid session
- **THEN** the system renders the staff dashboard: sidebar, workspace header, and visit-requests kanban board
