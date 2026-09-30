## ADDED Requirements

### Requirement: Editing a field brings its properties panel into view
The system SHALL, when a tenant admin explicitly selects a field in the step
editor (via the field's Edit button or its label), scroll the Field Properties
panel into the visible area of the editor's scroll region so the admin can see
and use it without manual scrolling. The system SHALL NOT scroll for the
automatic initial selection made when a step's fields first load.

#### Scenario: Edit button reveals a panel that is off-screen
- **WHEN** the Field Properties panel is outside the visible area and the admin clicks a field's Edit button
- **THEN** the editor scrolls smoothly until the panel for that field is visible

#### Scenario: Panel already visible
- **WHEN** the admin clicks Edit on a field and the panel is already fully visible
- **THEN** the view does not move and the panel shows that field's properties

#### Scenario: Initial load does not scroll
- **WHEN** a step's fields finish loading and the first field is auto-selected
- **THEN** the editor stays at its current scroll position

#### Scenario: Selecting a different field re-scrolls
- **WHEN** the admin has scrolled back up and clicks Edit on another field
- **THEN** the panel updates to that field and is scrolled into view again
