## REMOVED Requirements

### Requirement: Filters affordance is presented but not yet functional
**Reason**: Filters becomes a working control per the new requirement below.
**Migration**: No admin-facing migration beyond the list now changing when a filter is applied — see the new requirement's scenarios.

## ADDED Requirements

### Requirement: Security gate list can be filtered by building, gate type, and security level
The system SHALL, when "Filters" is activated, show a filter panel offering Building, Gate Type, and Security Level fields (each defaulting to "All"), and SHALL narrow the visible security gates to those matching every selected filter as soon as a filter changes, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Building, Gate Type, and Security Level filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Building, Gate Type, or Security Level value
- **THEN** the table immediately shows only security gates matching every currently selected filter

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Building, Gate Type, and Security Level
- **THEN** the table shows only security gates matching all of the selected filters at once

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** every filter resets to "All" and the table shows the full security gate list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters are active and no security gate matches them, show a message indicating no security gates match the current filters, distinct from the message shown when the organisation has zero security gates at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no security gate matches them
- **THEN** the system shows a "no security gates match these filters" message instead of the zero-security-gates empty state
