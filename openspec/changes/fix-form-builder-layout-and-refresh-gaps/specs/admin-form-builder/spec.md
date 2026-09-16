## Purpose

The admin-form-builder capability lets a tenant admin configure, at
`/admin/form-builder`, the branch-scoped registration steps and custom
fields a visitor registration/invitation form presents, and publish those
changes so they take effect for new registrations.

## ADDED Requirements

### Requirement: Page heading and primary controls stay fixed while step cards scroll
The system SHALL render the Form Builder page's title/description, tenant
selector, "Create Registration Step" action, and "Form Preview"/"Publish
Changes" controls in a fixed region that does not scroll, and SHALL render
the Registration Steps card grid in a separate, independently scrollable
region beneath it.

#### Scenario: Scrolling the step list does not move the heading controls
- **WHEN** a tenant admin scrolls the Registration Steps card grid on the
  Form Builder page
- **THEN** the title, tenant selector, "Create Registration Step" button,
  "Form Preview", and "Publish Changes" controls remain visible in place

#### Scenario: A tenant with many registration steps can still act on any of them
- **WHEN** a tenant has enough registration steps that the card grid exceeds
  the visible height of its scroll region
- **THEN** the admin can scroll the card grid to reach every step's card
  without losing access to "Create Registration Step" or "Publish Changes"

### Requirement: "Create Registration Step" is a compact action beside Publish Changes
The system SHALL render "Create Registration Step" as a compact button in
the fixed heading region, positioned alongside "Form Preview" and "Publish
Changes", rather than as a full-width control competing with the step-card
grid for vertical space.

#### Scenario: Create action is reachable without scrolling
- **WHEN** the Form Builder page loads with any number of registration steps
  (including zero)
- **THEN** "Create Registration Step" is visible in the fixed heading row
  without scrolling

### Requirement: The step-card grid uses a non-intrusive scrollbar
The system SHALL give the Registration Steps card grid its own bounded
scroll region styled with a thin, low-contrast scrollbar rather than the
browser's default scrollbar, so the scroll region reads as intentional
rather than as a layout defect.

#### Scenario: Step grid scrollbar is unobtrusive
- **WHEN** the Registration Steps card grid's content exceeds its visible
  height
- **THEN** a thin, low-contrast scroll indicator appears for that region
  instead of the browser's default wide scrollbar

### Requirement: Step editor page heading stays fixed while field configuration scrolls
The system SHALL apply the same fixed-heading/scrollable-body layout to the
registration-step field editor page (`/admin/form-builder/steps/:stepId`)
as the Form Builder list page.

#### Scenario: Scrolling field configuration does not move the step editor's heading
- **WHEN** a tenant admin scrolls a step's field list on the step editor
  page
- **THEN** the step editor's heading and save/publish-related controls
  remain visible in place
