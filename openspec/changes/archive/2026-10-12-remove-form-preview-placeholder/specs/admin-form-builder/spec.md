## MODIFIED Requirements

### Requirement: Page heading and primary controls stay fixed while step cards scroll
The system SHALL render the Form Builder page's title/description, tenant
selector, "Create Registration Step" action, and "Publish Changes" control
in a fixed region that does not scroll, and SHALL render the Registration
Steps card grid in a separate, independently scrollable region beneath it.
The heading region SHALL NOT contain a "Form Preview" control, or any other
control that is permanently disabled with no working behaviour behind it.

#### Scenario: Scrolling the step list does not move the heading controls
- **WHEN** a tenant admin scrolls the Registration Steps card grid on the
  Form Builder page
- **THEN** the title, tenant selector, "Create Registration Step" button,
  and "Publish Changes" control remain visible in place

#### Scenario: A tenant with many registration steps can still act on any of them
- **WHEN** a tenant has enough registration steps that the card grid exceeds
  the visible height of its scroll region
- **THEN** the admin can scroll the card grid to reach every step's card
  without losing access to "Create Registration Step" or "Publish Changes"

#### Scenario: No placeholder preview control is shown
- **WHEN** a tenant admin opens the Form Builder page
- **THEN** the heading row shows no "Form Preview" button, enabled or
  disabled

### Requirement: "Create Registration Step" is a compact action beside Publish Changes
The system SHALL render "Create Registration Step" as a compact button in
the fixed heading region, positioned alongside "Publish Changes", rather
than as a full-width control competing with the step-card grid for vertical
space.

#### Scenario: Create action is reachable without scrolling
- **WHEN** the Form Builder page loads with any number of registration steps
  (including zero)
- **THEN** "Create Registration Step" is visible in the fixed heading row
  without scrolling
