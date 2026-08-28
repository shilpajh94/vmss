# staff-sso-login Specification

## Purpose

The staff-sso-login capability gives staff a dedicated Enterprise Sign In screen at `/staff/login` that authenticates them against their organization's identity provider via SSO, replacing the shared password form as staff's entry point into the system.

## Requirements

### Requirement: Staff SSO login screen is reachable at a dedicated route
The system SHALL render the staff "Enterprise Sign In" screen at the `/staff/login` route, matching the approved "staff-sso-login" design: the existing gateway header/footer chrome, and a centered card with a "STAFF PORTAL" tag, an "Enterprise Sign In" title, a "Sign in with your organization credentials" description, a single "Sign in with SSO" action, and a "Secured by corporate multi-factor authentication" security note, plus a "Need help? Contact System Administrator" link below the card. The screen SHALL NOT present email or password fields.

#### Scenario: Staff navigates to the SSO login route
- **WHEN** a user navigates to `/staff/login` with no pending sign-in in progress
- **THEN** the system renders the Enterprise Sign In card with a single "Sign in with SSO" action and no email/password fields

### Requirement: Sign-in action starts SSO at the tenant's identity provider
The system SHALL, when the "Sign in with SSO" action is activated, navigate the browser to the backend's SSO login-start endpoint for the deployment's configured tenant, which redirects the browser to the tenant's identity provider.

#### Scenario: Staff starts SSO sign-in
- **WHEN** a staff member activates "Sign in with SSO"
- **THEN** the browser navigates to the SSO login-start endpoint for the configured tenant

### Requirement: Returning from the identity provider completes sign-in
The system SHALL detect a sign-in completion code carried back to `/staff/login` after the identity provider's round trip, show a loading state while completing sign-in, and exchange that code for a token pair. On a successful exchange, the system SHALL store the returned access token and navigate to `/staff/dashboard`.

#### Scenario: Staff completes SSO sign-in
- **WHEN** the browser returns to `/staff/login` carrying a sign-in completion code from the identity provider round trip
- **THEN** the system shows a loading state, exchanges the code for a token pair, stores the returned access token, and navigates to `/staff/dashboard`

### Requirement: SSO failure is reported without a stuck loading state
The system SHALL show an inline error message on the login screen if starting SSO or completing the sign-in exchange fails (denied or expired code, network error, or non-success response), and SHALL return the "Sign in with SSO" action to an activatable state so the staff member can retry. The system SHALL also trigger an error notification when this happens.

#### Scenario: SSO sign-in fails
- **WHEN** completing the sign-in exchange fails because of a denied or expired code, a network error, or a non-success response
- **THEN** the system shows an inline error message on the login screen, returns the "Sign in with SSO" action to an activatable state, and triggers an error notification
