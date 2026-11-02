# select-dropdowns Specification

## Purpose

Defines how every single-choice dropdown in the web app looks and behaves: a consistent, themed, product-style control. It opens from anywhere on its trigger, works fully from the keyboard, and is announced correctly by assistive technology.

## Requirements

### Requirement: Dropdowns use one consistent, themed product style
Every single-choice dropdown in the web app SHALL use one shared visual style built from the design-theme tokens. This covers form fields, filter bars, modals, the form builder and the visitor portal. No dropdown SHALL render the browser's native option list.

The closed trigger SHALL show:
- a rounded border;
- the selected option's label, or the placeholder in muted text when nothing is selected;
- an optional leading icon;
- a trailing chevron.

The trigger SHALL show distinct hover, focus-visible, open, error and disabled states.

The open list SHALL appear as a floating panel with rounded corners, a soft shadow, and the same surface and border colours as other popovers. Each option SHALL highlight on hover and while keyboard-active. The currently selected option SHALL show a check mark and emphasised text. All states SHALL render correctly in both light and dark theme modes.

#### Scenario: Same look on every operating system
- **WHEN** a user opens the Branch filter on the Invitations board in Chrome on Windows and in Safari on macOS
- **THEN** both show the same themed panel, option spacing, highlight colour and check mark, not each OS's native picker

#### Scenario: Placeholder versus a chosen value
- **WHEN** an admin opens the Add Floor form, where Building is not yet chosen
- **THEN** the Building trigger shows "Select building" in muted text, and once a building is chosen it shows that building's name in normal text

#### Scenario: Error state
- **WHEN** a required dropdown is submitted empty
- **THEN** the trigger shows the danger border and the error message beneath it, matching text inputs in the same form

#### Scenario: Dark mode
- **WHEN** the app is in dark theme mode and a user opens any dropdown
- **THEN** the trigger and panel use the dark surface, border and text colours, and the selected-option highlight remains legible

### Requirement: The whole trigger opens the dropdown
Pressing anywhere inside a dropdown's trigger SHALL open its option list. This includes the chevron, the leading icon, the label text and the padding. Pressing the trigger while the list is open SHALL close the list. A disabled dropdown SHALL NOT open.

#### Scenario: Clicking the chevron
- **WHEN** a reception user clicks directly on the chevron arrow of the Status filter
- **THEN** the option list opens, exactly as it does when clicking the label text in the middle

#### Scenario: Clicking the leading icon
- **WHEN** a user clicks the funnel icon at the start of a filter dropdown
- **THEN** the option list opens

#### Scenario: Toggling closed
- **WHEN** the list is open and the user clicks the trigger again
- **THEN** the list closes and the value is unchanged

### Requirement: Dropdowns open and close with motion and stay fully visible
The option list SHALL fade and scale in from the trigger's edge and out again, consistent with "Popovers and menus animate from their anchor" in ui-motion. Under the reduced-motion preference it SHALL appear and disappear instantly. The chevron SHALL rotate to point up while the list is open.

The panel SHALL be at least as wide as its trigger. It SHALL open below the trigger, or above it when there isn't enough space below. It SHALL scroll internally once it exceeds its maximum height. It SHALL never be clipped by a scrolling container, card or modal that the trigger sits inside. It SHALL stay attached to its trigger while the page scrolls or resizes, or close if the trigger scrolls out of view.

#### Scenario: Dropdown inside a modal
- **WHEN** a user opens the Delegate-to dropdown inside the Delegate Invitation modal
- **THEN** the whole option list is visible over the modal's edge rather than cut off by it

#### Scenario: Not enough room below
- **WHEN** a dropdown near the bottom of the viewport is opened
- **THEN** its panel opens above the trigger

#### Scenario: Long option list
- **WHEN** a dropdown with 40 host employees is opened
- **THEN** the panel shows a bounded number of options and scrolls to reveal the rest, with the selected option scrolled into view

### Requirement: Dropdowns are fully keyboard- and screen-reader-operable
Each dropdown SHALL be reachable with Tab. It SHALL expose a combobox role, its visible label as its accessible name, its expanded state, and its required, invalid and disabled states. Its options SHALL be exposed as a listbox of options, with the selected option marked selected.

With the trigger focused:
- Enter, Space, ArrowDown or ArrowUp SHALL open the list with the selected option, or the first option, active.

While the list is open:
- ArrowUp and ArrowDown SHALL move the active option;
- Home and End SHALL jump to the first and last option;
- typing printable characters SHALL jump to the next option whose label starts with them;
- Enter or Space SHALL choose the active option and close the list;
- Escape SHALL close the list without changing the value;
- Tab SHALL close the list and move focus on.

Focus SHALL return to the trigger after choosing or Escape. Clicking outside SHALL close the list without changing the value. Disabled options SHALL be skipped and not selectable. Choosing an option SHALL notify the form exactly once, with that option's value.

#### Scenario: Keyboard selection
- **WHEN** a user tabs to the Department dropdown, presses ArrowDown twice and then Enter
- **THEN** the list opens, the second option after the current one becomes active, Enter selects it, the list closes, and focus stays on the trigger

#### Scenario: Type-ahead
- **WHEN** the Building list is open and the user types "w"
- **THEN** the first building whose name starts with "W" becomes active and is scrolled into view

#### Scenario: Escape cancels
- **WHEN** a user opens a dropdown, arrows to a different option and presses Escape
- **THEN** the list closes and the original value is still selected

#### Scenario: Screen reader announcement
- **WHEN** a screen-reader user focuses the Visitor category field
- **THEN** it is announced as a combobox named "Visitor category", collapsed, with its current value, and as required if the field is required

### Requirement: The placeholder is reselectable only when it is a real choice
When a dropdown's placeholder represents a valid value, such as "All branches" or "Ungrouped", it SHALL appear as a selectable first option. When the placeholder is only a prompt, such as "Select building", it SHALL appear in the closed trigger only and SHALL NOT be offered as an option.

#### Scenario: Filter "All" option
- **WHEN** a user has filtered the board to one branch and opens the Branch filter
- **THEN** "All branches" is listed first and choosing it clears the filter

#### Scenario: Prompt-only placeholder
- **WHEN** a user opens the Building dropdown on the Add Floor form
- **THEN** the list contains only buildings, with no "Select building" entry
