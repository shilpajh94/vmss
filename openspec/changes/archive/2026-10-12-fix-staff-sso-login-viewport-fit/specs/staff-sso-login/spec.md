## MODIFIED Requirements

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
