## Purpose
Single-value dropdowns across the app share one themed look and interaction model, matching the invitation board's filter dropdowns, instead of the browser's native select menu.

## ADDED Requirements

### Requirement: Single-value dropdowns use the themed panel
Every single-value dropdown in the application (dashboard branch picker, calendar and audit-trail filters, admin and wizard form selects, delegate picker, form-builder group assignment) SHALL render a themed trigger and a floating themed option panel, not the browser's native select menu. The trigger SHALL show the selected option's label (or the placeholder when nothing is selected) and a chevron that rotates while open; filter-style triggers SHALL also show their icon. The panel SHALL use the same surface, border, shadow, row spacing and hover styling as the invitation board's filter dropdowns, and SHALL mark the selected option with a check and emphasised text.

#### Scenario: Branch picker opens a themed list
- **WHEN** a user opens the "All branches" picker on the dashboard
- **THEN** a rounded floating panel lists All branches and each branch with the current choice checked, and no native browser menu appears

#### Scenario: Form select matches
- **WHEN** a user opens a form select such as "Visitor category" in a modal
- **THEN** the same themed panel appears, fully visible even when the modal body scrolls or the field sits near the bottom of the screen

### Requirement: Selecting, closing and keyboard operation
Choosing an option SHALL set the value, close the panel and return focus to the trigger. The panel SHALL close on outside click, Escape or Tab. The trigger SHALL be operable by keyboard (Enter/Space/ArrowDown to open; ArrowUp/ArrowDown/Home/End to move; Enter/Space to choose) and expose listbox semantics (`aria-haspopup`, `aria-expanded`, `role="listbox"`/`option`, `aria-selected`). Typing a character SHALL move to the next option starting with it.

#### Scenario: Keyboard selection
- **WHEN** a user focuses the trigger, presses ArrowDown, moves to an option and presses Enter
- **THEN** that option becomes the value, the panel closes and focus returns to the trigger

#### Scenario: Outside click dismisses
- **WHEN** the panel is open and the user clicks elsewhere on the page
- **THEN** the panel closes and the value is unchanged

### Requirement: Form-field states are preserved
Form selects SHALL keep their label (with required marker), placeholder, inline error message and error border, and disabled state (not openable, dimmed). A placeholder entry that is a valid choice (e.g. "All branches") SHALL remain selectable; one that is only a prompt SHALL be shown on the trigger but not offered as a choosable row.

#### Scenario: Disabled select
- **WHEN** a select is disabled (e.g. while eligible employees load)
- **THEN** it cannot be opened and shows the dimmed style

#### Scenario: Validation error
- **WHEN** a required select has an error
- **THEN** its trigger shows the danger border and the error text appears beneath it

### Requirement: Small-screen and long-list behaviour
On narrow screens the trigger and rows SHALL keep touch-friendly height and 16px text. The panel SHALL be at least as wide as its trigger, scroll internally for long lists, and flip above the trigger when there is not enough room below.

#### Scenario: Long list near bottom
- **WHEN** a select near the bottom of the viewport has many options
- **THEN** the panel opens upward or is height-limited and scrolls, with every option reachable
