# staff-login Specification

## Purpose

The staff-login capability gives staff a dedicated, branded sign-in gateway into the system via SSO, distinct from the visitor-facing flows, and a placeholder landing area once signed in.

## Requirements

### Requirement: Staff login screen is reachable at a dedicated route
The system SHALL render the staff Enterprise Sign In screen at the `/admin/login` route, matching the approved "staff-sso-login" design: an Admin Gateway header, a centered sign-in card, and a footer with legal links.

The screen SHALL fit within the browser viewport. When the viewport is at least 1024px wide and at least 700px tall, the Admin Gateway header, the entire sign-in card (through the "Secured by corporate authentication" line), the "Need help?" line, and the footer SHALL all be visible at once, with no page scrolling. The header SHALL sit at the top edge of the viewport and the footer at the bottom edge. The sign-in card and help line SHALL be centered vertically in the space between them. The lobby background image SHALL cover the full viewport.

When the viewport is too short to show all of this content at once, the page SHALL keep the header and footer in place and let only the region holding the sign-in card scroll. No part of the sign-in card SHALL become unreachable or clipped.

#### Scenario: Staff navigates to the login route
- **WHEN** a user navigates to `/admin/login`
- **THEN** the system renders the Admin Gateway header, the "Enterprise Sign In" card with a sign-in action, and the footer

#### Scenario: The old route no longer serves the login screen
- **WHEN** a user navigates to `/staff/login`
- **THEN** the system does not render the Enterprise Sign In screen at that path

#### Scenario: Login screen fits a laptop viewport without scrolling
- **WHEN** a user opens `/admin/login` in a viewport of 1920×870 (or any viewport at least 1024px wide and 700px tall)
- **THEN** the header, the full sign-in card including the "Sign in with SSO" button and the "Secured by corporate authentication" line, the "Need help?" line, and the footer are all visible, and the page has no vertical scrollbar

#### Scenario: Login screen shows a validation error without forcing page scroll
- **WHEN** a user submits the form with both fields empty in a viewport of 1920×870
- **THEN** the field validation messages appear and the footer remains visible without page scrolling

#### Scenario: Short viewport scrolls only the content region
- **WHEN** a user opens `/admin/login` in a viewport shorter than the content can fit (for example 800×500)
- **THEN** the header stays at the top and the footer stays at the bottom, and the user can scroll the region containing the sign-in card to reach every part of it

#### Scenario: Phone viewport keeps the card fully reachable
- **WHEN** a user opens `/admin/login` in a 360×640 viewport
- **THEN** every field and button of the sign-in card can be reached by scrolling, and nothing is clipped or hidden behind the header or footer

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL render the staff login screen with its own dark-themed header, carrying the Visimio on-dark logo (mark plus white wordmark), an "Admin Gateway" badge, and a system-status indicator. It SHALL NOT reuse the visitor portal's light header component.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the staff login screen renders
- **THEN** the visitor portal's light header is not present, and the dark Admin Gateway header is shown instead, with the Visimio on-dark logo

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

### Requirement: Successful sign-in lands on a role-based dashboard
The system SHALL, once a login request succeeds and the auth token is stored, determine the signed-in user's roles and navigate to `/admin/dashboard` when the user has the Admin role, to `/reception/dashboard` when the user has the Reception role (and not the Admin role), or to `/staff/dashboard` otherwise.

#### Scenario: Admin reaches the Admin Dashboard
- **WHEN** a user with the Admin role signs in successfully
- **THEN** the system navigates to `/admin/dashboard`

#### Scenario: Reception user reaches the Reception Dashboard
- **WHEN** a user with the Reception role, but not the Admin role, signs in successfully
- **THEN** the system navigates to `/reception/dashboard`

#### Scenario: Other staff reach the staff dashboard
- **WHEN** a user with neither the Admin nor the Reception role signs in successfully
- **THEN** the system navigates to `/staff/dashboard`

### Requirement: An expired or unauthorized session redirects to the login screen
The system SHALL redirect the browser to `/staff/login` whenever a staff-only page detects a missing, expired, or unauthorized session, and to `/admin/login` whenever an admin-only page detects a missing, expired, or unauthorized session.

#### Scenario: Session guard redirects on an admin or staff page
- **WHEN** an admin-only page loads without a valid session, or a request from that page fails with an unauthorized response
- **THEN** the system redirects the browser to `/admin/login`

#### Scenario: Session guard redirects on a staff-only page
- **WHEN** a staff-only page (staff dashboard, staff audit trail, staff visitor registration) loads without a valid session, or a request from that page fails with an unauthorized response
- **THEN** the system redirects the browser to `/staff/login`

### Requirement: Admin sign-in actions show a pointer cursor
On the `/admin/login` screen, the "Sign In" button and the "Sign in with SSO" button SHALL show the pointer (hand) cursor while the mouse is over them and they are enabled. While either button is disabled (a sign-in is in progress), it SHALL show the not-allowed cursor instead.

#### Scenario: Hovering the Sign In button
- **WHEN** a user moves the mouse over the enabled "Sign In" button on `/admin/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering the SSO button
- **WHEN** a user moves the mouse over the enabled "Sign in with SSO" button on `/admin/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering a button while sign-in is in progress
- **WHEN** a password sign-in is in progress and the user moves the mouse over the disabled "Sign In" or "Sign in with SSO" button
- **THEN** the mouse cursor is the not-allowed cursor, not the pointer cursor
