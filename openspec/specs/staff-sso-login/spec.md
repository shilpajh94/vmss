# staff-sso-login Specification

## Purpose

The staff-sso-login capability gives staff a dedicated Enterprise Sign In screen at `/staff/login` that authenticates them against their organization's identity provider via SSO, replacing the shared password form as staff's entry point into the system.

## Requirements

### Requirement: Staff SSO login screen is reachable at a dedicated route
The system SHALL render the staff "Enterprise Sign In" screen at the `/staff/login` route, matching the approved "staff-sso-login" design: the existing gateway header/footer chrome, and a centered card with a "STAFF PORTAL" tag, an "Enterprise Sign In" title, a "Sign in with your organization credentials" description, a single "Sign in with SSO" action, and a "Secured by corporate multi-factor authentication" security note, plus a "Need help? Contact System Administrator" link below the card. The screen SHALL NOT present email or password fields.

The screen SHALL fit within the browser viewport. When the viewport is at least 1024px wide and at least 700px tall, the Staff Gateway header, the entire sign-in card (through the "Secured by corporate multi-factor authentication" note), the "Need help?" line, and the footer SHALL all be visible at once, with no page scrolling. The header SHALL sit at the top edge of the viewport and the footer at the bottom edge. The sign-in card and help line SHALL be centered vertically in the space between them. The lobby background image SHALL cover the full viewport.

When the viewport is too short to show all of this content at once, the page SHALL keep the header and footer in place and let only the region holding the sign-in card scroll. No part of the sign-in card SHALL become unreachable or clipped.

#### Scenario: Staff navigates to the SSO login route
- **WHEN** a user navigates to `/staff/login` with no pending sign-in in progress
- **THEN** the system renders the Enterprise Sign In card with a single "Sign in with SSO" action and no email/password fields

#### Scenario: SSO login screen fits a laptop viewport without scrolling
- **WHEN** a user opens `/staff/login` in a viewport of 1920×870 (or any viewport at least 1024px wide and 700px tall)
- **THEN** the header, the full sign-in card including the "Sign in with SSO" button and the "Secured by corporate multi-factor authentication" note, the "Need help?" line, and the footer are all visible, and the page has no vertical scrollbar

#### Scenario: SSO error message does not force page scroll
- **WHEN** a sign-in attempt fails and the inline error message is shown, in a viewport of 1920×870
- **THEN** the error message, the "Sign in with SSO" action, and the footer are all visible without page scrolling

#### Scenario: Short viewport scrolls only the content region
- **WHEN** a user opens `/staff/login` in a viewport shorter than the content can fit (for example 800×500)
- **THEN** the header stays at the top and the footer stays at the bottom, and the user can scroll the region containing the sign-in card to reach every part of it

#### Scenario: Phone viewport keeps the card fully reachable
- **WHEN** a user opens `/staff/login` in a 360×640 viewport
- **THEN** the "Sign in with SSO" action and every other part of the sign-in card can be reached by scrolling, and nothing is clipped or hidden behind the header or footer

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
