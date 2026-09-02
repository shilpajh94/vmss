## REMOVED Requirements

### Requirement: Filters affordance is presented but not yet functional
**Reason**: Filters becomes a working control per the new requirement below.
**Migration**: No admin-facing migration beyond the list now changing when a filter is applied — see the new requirement's scenarios.

## ADDED Requirements

### Requirement: Branch list can be filtered by status
The system SHALL, when "Filters" is activated, show a filter panel offering a Status field (Active/Inactive, defaulting to "All"), and SHALL narrow the visible branches to those matching the selected status as soon as it changes, without a separate confirm step. The system SHALL let an admin clear the active filter back to "All".

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Status filter field

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Status value
- **THEN** the table immediately shows only branches matching that status

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the filter resets to "All" and the table shows the full branch list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when a filter is active and no branch matches it, show a message indicating no branches match the current filters, distinct from the message shown when the organisation has zero branches at all.

#### Scenario: No matches for active filter
- **WHEN** a filter is active and no branch matches it
- **THEN** the system shows a "no branches match these filters" message instead of the zero-branches empty state
