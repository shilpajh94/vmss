## Purpose

Sets the accessibility baseline every staff, admin and public page must
meet, so keyboard, screen-reader and low-vision users can operate the
product: visible focus, sufficient contrast, labelled controls, announced
async states and correct interactive nesting.

## ADDED Requirements

### Requirement: Every Interactive Control Shows a Visible Keyboard Focus Indicator
Every button, link, input, select, textarea, toggle, checkbox and custom
control SHALL show a visible focus indicator when it receives keyboard
focus. A control that suppresses the browser outline SHALL replace it with
an equivalent ring of at least 2px in the theme's accent colour, in both
light and dark mode.

#### Scenario: Tabbing through a filter bar
- **WHEN** a keyboard user tabs through an admin list page's filter
  dropdowns and search box
- **THEN** each control shows a visible focus ring as it receives focus

#### Scenario: Toggle switch focus
- **WHEN** a keyboard user tabs onto a toggle switch whose native input is
  visually hidden
- **THEN** the visible switch track shows a focus ring

### Requirement: Text Meets WCAG AA Contrast
Text rendered with the theme's text tokens SHALL meet a contrast ratio of at
least 4.5:1 against the surface it is drawn on (3:1 for text 18.66px bold or
24px and larger), in both light and dark mode. This includes faint/secondary
text and status-badge text on tinted backgrounds. Purely decorative glyphs
are exempt.

#### Scenario: Faint text on a card
- **WHEN** a tracking ID or schedule is rendered in the faint text colour
  on a card surface
- **THEN** its contrast ratio is at least 4.5:1

#### Scenario: Active status badge
- **WHEN** an "Active" badge is rendered with success-coloured text on its
  tinted background
- **THEN** its contrast ratio is at least 4.5:1

### Requirement: Every Form Control Has an Accessible Name, and Required Fields Are Marked
Every input, select and textarea SHALL have an accessible name from a
visible label or `aria-label`; a placeholder alone is not enough. A field
the form requires SHALL be marked both visibly (`*`) and programmatically
(`aria-required` or `required`). An inline field error SHALL be linked to
its control through `aria-describedby`.

#### Scenario: Board search input
- **WHEN** a screen-reader user focuses the invitation board's search box
- **THEN** it is announced with a name describing what it searches

#### Scenario: Required branch address
- **WHEN** an admin views the branch form
- **THEN** the Physical Address label shows `*` and the control is
  announced as required

### Requirement: Async Errors and Loading States Are Announced
A shared error state SHALL render with `role="alert"`. A shared loading
indicator SHALL render with `role="status"`. Assistive technology then
announces a failed load or an in-progress load without the user having to
find it.

#### Scenario: List load fails
- **WHEN** an admin list page's initial load fails
- **THEN** the error message and its retry action are inside an element
  with `role="alert"`

### Requirement: Interactive Elements Are Not Nested Inside Other Interactive Elements
A clickable region SHALL NOT contain another button, link or menu trigger.
A card that opens a detail view and also offers actions SHALL make its
title the single control that opens the detail, and keep its actions as
sibling controls.

#### Scenario: Board card with actions
- **WHEN** a keyboard user tabs through an invitation card
- **THEN** the card title, then each action button, receive focus as
  separate controls, and activating an action does not also open the
  detail
