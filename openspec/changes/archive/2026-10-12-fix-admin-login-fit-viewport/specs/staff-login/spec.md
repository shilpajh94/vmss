## MODIFIED Requirements

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
