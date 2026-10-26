## MODIFIED Requirements

### Requirement: Staff login screen is reachable at a dedicated route
The system SHALL render the admin sign-in screen at the `/admin/login` route as a split-screen layout. The layout has a brand panel and a form panel.

The form panel SHALL hold, in order:
- an "Admin Portal" tag;
- a "Welcome back" heading with a one-line description;
- the sign-in form;
- a security note;
- a "Need help? Contact System Administrator" link, shown when a support address is configured;
- footer links to the configured legal pages.

When the viewport is at least 1024px wide:
- the brand panel SHALL occupy the left part of the viewport;
- the form panel SHALL occupy the right part.

When the viewport is narrower:
- the brand panel SHALL collapse to a slim strip at the top, carrying the logo and the "Admin Portal" tag;
- the form panel SHALL fill the rest of the screen.

The screen SHALL fit within the browser viewport. When the viewport is at least 1024px wide and at least 700px tall, all of the following SHALL be visible at once, with no page scrolling:
- the brand panel;
- the whole sign-in form, through the security note;
- the help link;
- the footer links.

The brand panel SHALL fill the full viewport height. Its lobby photo SHALL cover the panel.

When the viewport is too short to show all of the form panel at once:
- only the form panel SHALL scroll;
- the brand panel (or, on narrow viewports, the top strip) SHALL stay in place;
- no part of the sign-in form SHALL become unreachable or clipped.

#### Scenario: Staff navigates to the login route
- **WHEN** a user navigates to `/admin/login`
- **THEN** the system renders the brand panel and a form panel with the "Admin Portal" tag, the "Welcome back" heading, and the "Sign In" action

#### Scenario: The old route no longer serves the login screen
- **WHEN** a user navigates to `/staff/login`
- **THEN** the system does not render the admin sign-in screen at that path

#### Scenario: Login screen fits a laptop viewport without scrolling
- **WHEN** a user opens `/admin/login` in a viewport of 1920×870 (or any viewport at least 1024px wide and 700px tall)
- **THEN** the brand panel, the full sign-in form including the "Sign In" action and the security note, the help link, and the footer links are all visible, and the page has no vertical scrollbar

#### Scenario: Login screen shows a validation error without forcing page scroll
- **WHEN** a user submits the form with both fields empty in a viewport of 1920×870
- **THEN** the field validation messages appear and the footer links remain visible without page scrolling

#### Scenario: Short viewport scrolls only the content region
- **WHEN** a user opens `/admin/login` in a viewport shorter than the form panel can fit (for example 1280×560)
- **THEN** the brand panel stays in place and the user can scroll the form panel to reach every part of the sign-in form

#### Scenario: Narrow viewport collapses the brand panel
- **WHEN** a user opens `/admin/login` in a viewport narrower than 1024px
- **THEN** the brand panel is replaced by a top strip showing the logo and the "Admin Portal" tag, and the form panel spans the full width below it

#### Scenario: Phone viewport keeps the card fully reachable
- **WHEN** a user opens `/admin/login` in a 360×640 viewport
- **THEN** every field and button of the sign-in form can be reached by scrolling, and nothing is clipped or hidden behind the top strip

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL give the admin sign-in screen its own brand panel, distinct from the visitor portal's light header. It SHALL NOT reuse the visitor portal's header component.

The brand panel SHALL show:
- the lobby photo under a navy gradient overlay;
- the Guestify on-dark logo (the teal "G" pin mark, teal "Gu" and white "estify");
- a headline and a one-line tagline;
- three product highlights, each with an icon and a short label;
- the copyright line.

The screen SHALL NOT show a system-status indicator. Nothing on this page checks system health, so the indicator would be a static, unverified claim.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the admin sign-in screen renders in a viewport at least 1024px wide
- **THEN** the visitor portal's light header is not present, and the brand panel is shown instead, with the Guestify on-dark logo, a headline, three product highlights, and the copyright line

#### Scenario: No static status claim
- **WHEN** the admin sign-in screen renders
- **THEN** no "All Systems Operational" or other system-status indicator is shown

### Requirement: Login failure is reported without a stuck loading state
The system SHALL show an inline error message on the login screen if the login request fails. Failure covers invalid credentials, a network error, or a non-success response. The message SHALL be announced to assistive technology as an alert. The system SHALL return the "Sign In" action to an activatable state so the staff member can retry.

#### Scenario: Login request fails
- **WHEN** the login request fails because of invalid credentials, a network error, or a non-success response
- **THEN** the system shows an inline error message on the login screen, exposed with the alert role, and re-enables the "Sign In" action

## ADDED Requirements

### Requirement: Password can be revealed while typing
The system SHALL provide a toggle inside the admin sign-in password field.

The toggle:
- SHALL switch the field between hidden and visible text;
- SHALL be a keyboard-operable button with an accessible name, "Show password" or "Hide password", that reflects the action it will perform;
- SHALL NOT submit the form;
- SHALL NOT clear or alter the entered value.

The password field SHALL start hidden each time the page loads. The email and password fields SHALL carry the `username` and `current-password` autocomplete hints, so password managers can fill them.

#### Scenario: Revealing the password
- **WHEN** a user has typed a password and activates "Show password"
- **THEN** the password is shown as plain text, the value is unchanged, the form is not submitted, and the toggle's accessible name becomes "Hide password"

#### Scenario: Password hidden on load
- **WHEN** a user opens `/admin/login`
- **THEN** the password field masks its input and the toggle's accessible name is "Show password"
