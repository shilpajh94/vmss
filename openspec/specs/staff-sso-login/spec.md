# staff-sso-login Specification

## Purpose

The staff-sso-login capability gives staff a dedicated Enterprise Sign In screen at `/staff/login` that authenticates them against their organization's identity provider via SSO, replacing the shared password form as staff's entry point into the system.

## Requirements

### Requirement: Staff SSO login screen is reachable at a dedicated route
The system SHALL render the staff SSO sign-in screen at the `/staff/login` route. It SHALL use the same split-screen layout as the admin sign-in screen: a brand panel and a form panel.

The brand panel SHALL show:
- the lobby photo under a navy gradient overlay;
- the Guestify on-dark logo;
- a headline and tagline;
- three product highlights;
- the copyright line.

It SHALL NOT show a system-status indicator.

The form panel SHALL hold:
- a "Staff Portal" tag;
- a "Welcome back" heading with a "Sign in with your organization credentials" description;
- a single "Sign in with SSO" action;
- a "Secured by corporate multi-factor authentication" security note;
- a "Need help? Contact System Administrator" link, shown when a support address is configured;
- footer links to the configured legal pages.

The screen SHALL NOT present email or password fields.

When the viewport is at least 1024px wide:
- the brand panel SHALL occupy the left part of the viewport;
- the form panel SHALL occupy the right part.

When the viewport is narrower:
- the brand panel SHALL collapse to a slim strip at the top, carrying the logo and the "Staff Portal" tag;
- the form panel SHALL fill the rest of the screen.

The screen SHALL fit within the browser viewport. When the viewport is at least 1024px wide and at least 700px tall, all of the following SHALL be visible at once, with no page scrolling:
- the brand panel;
- the whole form panel, through the security note;
- the help link;
- the footer links.

When the viewport is too short:
- only the form panel SHALL scroll;
- the brand panel (or top strip) SHALL stay in place;
- no part of the form panel SHALL become unreachable or clipped.

#### Scenario: Staff navigates to the SSO login route
- **WHEN** a user navigates to `/staff/login` with no pending sign-in in progress
- **THEN** the system renders the brand panel and a form panel with the "Staff Portal" tag, the "Welcome back" heading, a single "Sign in with SSO" action, and no email/password fields

#### Scenario: SSO login screen fits a laptop viewport without scrolling
- **WHEN** a user opens `/staff/login` in a viewport of 1920×870 (or any viewport at least 1024px wide and 700px tall)
- **THEN** the brand panel, the "Sign in with SSO" action, the "Secured by corporate multi-factor authentication" note, the help link, and the footer links are all visible, and the page has no vertical scrollbar

#### Scenario: SSO error message does not force page scroll
- **WHEN** a sign-in attempt fails and the inline error message is shown, in a viewport of 1920×870
- **THEN** the error message (exposed with the alert role), the "Sign in with SSO" action, and the footer links are all visible without page scrolling

#### Scenario: Short viewport scrolls only the content region
- **WHEN** a user opens `/staff/login` in a viewport shorter than the form panel can fit (for example 1280×480)
- **THEN** the brand panel stays in place and the user can scroll the form panel to reach every part of it

#### Scenario: Narrow viewport collapses the brand panel
- **WHEN** a user opens `/staff/login` in a viewport narrower than 1024px
- **THEN** the brand panel is replaced by a top strip showing the logo and the "Staff Portal" tag, and the form panel spans the full width below it

#### Scenario: Phone viewport keeps the card fully reachable
- **WHEN** a user opens `/staff/login` in a 360×640 viewport
- **THEN** the "Sign in with SSO" action and every other part of the form panel can be reached by scrolling, and nothing is clipped or hidden behind the top strip

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

### Requirement: Staff SSO sign-in action shows a pointer cursor
On the `/staff/login` screen, the "Sign in with SSO" button SHALL show the pointer (hand) cursor while the mouse is over it and it is enabled. While the button is disabled (redirecting to the identity provider or completing sign-in), it SHALL show the not-allowed cursor instead.

#### Scenario: Hovering the SSO button
- **WHEN** a user moves the mouse over the enabled "Sign in with SSO" button on `/staff/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering the SSO button while redirecting
- **WHEN** an SSO redirect or sign-in completion is in progress and the user moves the mouse over the disabled "Sign in with SSO" button
- **THEN** the mouse cursor is the not-allowed cursor, not the pointer cursor
