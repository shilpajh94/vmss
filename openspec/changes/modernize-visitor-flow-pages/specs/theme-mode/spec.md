## MODIFIED Requirements

### Requirement: Public pages always render in the light theme
The visitor portal, visitor request wizard, tracking and OTP pages, the
staff and admin login pages, the not-found page, and the route error page
SHALL always render in the light theme, whatever the stored choice or
device setting. Their navy brand panel and top strip are fixed brand
surfaces, not dark-theme surfaces.

- Navigating from a themed staff or admin page to a public page SHALL
  switch to light.
- Navigating back SHALL restore the user's mode.
- The route error page SHALL render light even when it replaces a themed
  staff or admin page, and even though the rest of the app failed to
  render.

#### Scenario: Sign-out returns to a light login page
- **WHEN** a user with Dark selected signs out and lands on `/staff/login`
- **THEN** the login page renders in the light theme

#### Scenario: Visitor portal on a dark device
- **WHEN** a visitor opens the portal landing page on a device set to dark
- **THEN** the page renders in the light theme

#### Scenario: Error page with Dark selected
- **WHEN** a user with Dark selected opens a page whose code fails to load,
  and the "Something went wrong" page is shown
- **THEN** that page renders in the light theme, its content panel is
  light, and its brand panel (or top strip) shows exactly one visible
  Guestify logo, the white-wordmark variant

#### Scenario: Error page on a dark device
- **WHEN** the "Something went wrong" page is shown with System selected
  on a device set to dark
- **THEN** the page renders in the light theme
