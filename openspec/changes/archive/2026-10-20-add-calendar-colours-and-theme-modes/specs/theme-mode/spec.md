## Purpose

Lets each staff member choose a Light, Dark or System (follow the device)
colour theme for the signed-in staff and admin portals. The choice is
remembered in their browser and applied without a flash of the wrong
theme.

## ADDED Requirements

### Requirement: Staff choose Light, Dark or System from the top bar
Every page rendered in the staff layout or the admin layout SHALL show a
theme control in the top bar. That covers host, reception, security and
admin users.

- Activating the control SHALL offer three options: Light, Dark and
  System. The current option SHALL be indicated.
- Choosing an option SHALL apply it immediately, without a page reload.
- The control SHALL be operable by keyboard, and its options SHALL be
  announced with their selected state.

#### Scenario: Switching to dark
- **WHEN** a signed-in reception user opens the theme control and chooses
  Dark
- **THEN** the page switches to the dark theme at once, and the control
  shows Dark as selected

#### Scenario: Control is available on every staff and admin page
- **WHEN** a host views `/staff/calendar` and an admin views
  `/admin/branches`
- **THEN** both top bars show the theme control

#### Scenario: Keyboard use
- **WHEN** a user focuses the theme control, opens it with Enter, moves to
  System with the arrow keys and presses Enter
- **THEN** System becomes the selected mode

### Requirement: System mode follows the device colour scheme
In System mode, the system SHALL apply the dark theme when the device
reports `prefers-color-scheme: dark` and the light theme otherwise. It
SHALL update live when the device setting changes while the page is open.
System SHALL be the default when no choice has been stored.

#### Scenario: First visit on a dark device
- **WHEN** a user with no stored choice signs in on a device set to dark
- **THEN** the portal renders in the dark theme and the control shows
  System selected

#### Scenario: Device switches while the page is open
- **WHEN** System is selected and the device changes from light to dark
- **THEN** the page switches to the dark theme without a reload

#### Scenario: Explicit choice ignores the device
- **WHEN** Light is selected and the device is set to dark
- **THEN** the page stays in the light theme

### Requirement: The choice is remembered in this browser
The selected mode SHALL be stored in the browser and SHALL be restored on
reload, on new tabs, and after signing out and back in on the same browser.
The choice SHALL NOT be sent to the server. If browser storage is
unavailable or holds an unrecognised value, the system SHALL fall back to
System without an error.

#### Scenario: Reload keeps the choice
- **WHEN** a user selects Dark and reloads the page
- **THEN** the page renders in the dark theme and Dark is selected

#### Scenario: Storage unavailable
- **WHEN** browser storage throws on access
- **THEN** the portal renders using System mode and no error is shown

### Requirement: No flash of the wrong theme
On a full page load of a staff or admin page, the stored or system-derived
theme SHALL be applied before the first paint. A dark-theme user SHALL
never see a light frame first. The browser's native controls (scrollbars,
form controls) SHALL match the active theme.

#### Scenario: Hard reload in dark mode
- **WHEN** a user with Dark selected hard-reloads `/admin/dashboard`
- **THEN** the very first painted frame already uses the dark background

### Requirement: Public pages always render in the light theme
The visitor portal, visitor request wizard, tracking and OTP pages, and the
staff and admin login pages SHALL always render in the light theme,
whatever the stored choice or device setting.

- Navigating from a themed staff or admin page to a public page SHALL
  switch to light.
- Navigating back SHALL restore the user's mode.

#### Scenario: Sign-out returns to a light login page
- **WHEN** a user with Dark selected signs out and lands on `/staff/login`
- **THEN** the login page renders in the light theme

#### Scenario: Visitor portal on a dark device
- **WHEN** a visitor opens the portal landing page on a device set to dark
- **THEN** the page renders in the light theme

### Requirement: Every staff and admin surface follows the theme
In the dark theme, page backgrounds, cards, tables, modals, dropdowns, form
fields, toasts, the top bar and charts on staff and admin pages SHALL use
the dark token values. No surface SHALL remain a fixed light colour.

- Text SHALL meet WCAG AA contrast against its background: 4.5:1 for body
  text, 3:1 for large text and for UI component boundaries.
- Dashboard charts SHALL re-colour when the theme changes, without a
  reload.
- The sidebar keeps its existing dark navy styling in both themes.

#### Scenario: Modal in dark mode
- **WHEN** a dark-theme admin opens the "Add Floor" modal
- **THEN** the modal, its fields and its buttons use dark surfaces with
  readable text, and no white panel appears

#### Scenario: Charts follow a theme switch
- **WHEN** an admin on the dashboard switches from Light to Dark
- **THEN** the chart gridlines, axis text and tooltip surface switch to
  their dark colours without a reload
