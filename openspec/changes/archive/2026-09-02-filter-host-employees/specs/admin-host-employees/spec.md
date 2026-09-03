## REMOVED Requirements

### Requirement: Filters and Import Hosts are presented but not yet functional
**Reason**: Filters becomes a working control per the new "Host employee list can be filtered by department, role, and status" requirement below. Import Hosts remains non-functional and is now covered by its own requirement so it no longer shares wording with Filters.
**Migration**: No admin-facing migration for Import Hosts (still inert). Filters now changes the visible list — see the new requirement for its scenarios.

## ADDED Requirements

### Requirement: Import Hosts is presented but not yet functional
The system SHALL display the "Import Hosts" control per the design, but SHALL NOT import any host employees when it is activated.

#### Scenario: Import Hosts activated
- **WHEN** an admin activates "Import Hosts"
- **THEN** no host employees are imported and the visible list does not change

### Requirement: Host employee list can be filtered by department, role, and status
The system SHALL, when "Filters" is activated, show a filter panel offering Department, Role, and Status fields (each defaulting to "All"), and SHALL narrow the visible host employees to those matching every selected filter as soon as a filter changes, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters"
- **THEN** the system shows the Department, Role, and Status filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a specific Department, Role, or Status value
- **THEN** the table immediately shows only host employees matching every currently selected filter

#### Scenario: Multiple filters combine
- **WHEN** an admin has selected values for more than one of Department, Role, and Status
- **THEN** the table shows only host employees matching all of the selected filters at once

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** every filter resets to "All" and the table shows the full host employee list again

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters are active and no host employee matches them, show a message indicating no host employees match the current filters, distinct from the message shown when the organisation has zero host employees at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no host employee matches them
- **THEN** the system shows a "no host employees match these filters" message instead of the zero-host-employees empty state
