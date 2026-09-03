## REMOVED Requirements

### Requirement: Filters affordance is presented but not yet functional
**Reason**: Filters becomes a working control per the new requirement below.
**Migration**: No admin-facing migration beyond the list now changing when a filter is applied — see the new requirement's scenarios.

## ADDED Requirements

### Requirement: Visitor category list can be filtered by badge color, NDA requirement, and escort requirement
The system SHALL, when "Filters" is activated, show a filter panel offering Badge Color, NDA Requirement, and Escort Requirement fields (each defaulting to "All"), and SHALL narrow the visible visitor categories to those matching every selected filter as soon as a filter changes, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Badge Color, NDA Requirement, and Escort Requirement filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Badge Color, NDA Requirement, or Escort Requirement value
- **THEN** the table immediately shows only visitor categories matching every currently selected filter

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Badge Color, NDA Requirement, and Escort Requirement
- **THEN** the table shows only visitor categories matching all of the selected filters at once

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** every filter resets to "All" and the table shows the full visitor category list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters are active and no visitor category matches them, show a message indicating no visitor categories match the current filters, distinct from the message shown when the organisation has zero visitor categories at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no visitor category matches them
- **THEN** the system shows a "no visitor categories match these filters" message instead of the zero-visitor-categories empty state
