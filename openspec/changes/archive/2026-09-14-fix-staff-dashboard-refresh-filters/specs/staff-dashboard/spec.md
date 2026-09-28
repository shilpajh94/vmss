## MODIFIED Requirements

### Requirement: Refresh reloads the visit-requests list
The system SHALL present exactly one refresh control on the dashboard. When that control is activated, the system SHALL re-fetch the visit-requests list from the backend and re-render the board with the latest data.

#### Scenario: Only one refresh control is shown
- **WHEN** the dashboard finishes loading
- **THEN** exactly one refresh control is visible on the page

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates the refresh control
- **THEN** the system re-fetches the visit-requests list and updates the board with the result

## ADDED Requirements

### Requirement: Board refreshes automatically in the background
The system SHALL periodically re-fetch the visit-requests list on a fixed interval without requiring staff to activate the refresh control, and SHALL update the board with the result without showing the full-board loading state. The system SHALL NOT trigger an automatic refresh while a deny, reschedule, or delegate action is in progress or its dialog is open.

#### Scenario: Board updates without manual refresh
- **WHEN** the automatic refresh interval elapses while the dashboard is open
- **THEN** the system re-fetches the visit-requests list and updates the board with the result, without showing the full-board loading state

#### Scenario: Automatic refresh is suppressed during an in-progress action
- **WHEN** the automatic refresh interval elapses while a deny, reschedule, or delegate dialog is open
- **THEN** the system does not re-fetch the visit-requests list until that dialog is closed

### Requirement: Filters narrow the board by purpose of visit and registration type
The system SHALL provide a "Filters" control that lets a staff member select a Purpose of Visit and/or a Registration Type (Individual / Group). When one or both are selected, the system SHALL show only visit requests matching all selected criteria, combined with any active search text, across all columns. Clearing a filter SHALL restore requests that only failed to match that criterion.

#### Scenario: Filtering by purpose of visit
- **WHEN** a staff member selects a Purpose of Visit filter value
- **THEN** only visit requests whose purpose of visit matches that value remain visible, in their existing columns

#### Scenario: Filtering by registration type
- **WHEN** a staff member selects a Registration Type filter value
- **THEN** only visit requests whose registration type matches that value remain visible, in their existing columns

#### Scenario: Combined with search
- **WHEN** a staff member has both a search term and a filter active
- **THEN** only visit requests matching both the search term and the active filter(s) remain visible

#### Scenario: Filters cleared
- **WHEN** a staff member clears all active filters
- **THEN** all visit requests matching only the current search text (if any) are shown again

## REMOVED Requirements

### Requirement: Filters affordance is presented but not yet functional
**Reason**: Superseded by the functional filtering requirement above ("Filters narrow the board by purpose of visit and registration type").
**Migration**: No migration needed; this was a placeholder describing the control's inert state before filtering was implemented.
