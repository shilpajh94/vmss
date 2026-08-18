# async-ui-states Specification

## Purpose

The async-ui-states capability defines shared, consistent presentation for two conditions every list- or data-driven page hits: an operation still in progress, and a result set with zero items.

## Requirements

### Requirement: A shared loading indicator represents in-progress async operations
The system SHALL render a shared loading indicator in place of a view's content while that view's data-fetching operation is in progress, and SHALL remove it once the operation completes, whether it succeeds or fails.

#### Scenario: Operation in progress
- **WHEN** a view's data-fetching operation has started and not yet completed
- **THEN** the system shows the shared loading indicator in place of that view's content

#### Scenario: Operation completes
- **WHEN** a view's data-fetching operation completes, successfully or not
- **THEN** the system removes the shared loading indicator

### Requirement: A shared empty-state component represents a zero-item result
The system SHALL render a shared empty-state component (message, optional icon, optional action) in place of a list's, table's, or board's content whenever that collection has successfully loaded with zero items, instead of rendering no content or an empty container.

#### Scenario: Collection loads with zero items
- **WHEN** a list, table, or board successfully loads and has zero items to display
- **THEN** the system shows the shared empty-state component in place of that collection's content

#### Scenario: Collection loads with at least one item
- **WHEN** a list, table, or board successfully loads with one or more items
- **THEN** the system renders those items instead of the empty-state component

### Requirement: Empty state is not shown for a failed load
The system SHALL NOT render the empty-state component when a view's data-fetching operation fails; a failed operation SHALL be represented by that view's error reporting instead.

#### Scenario: Load fails
- **WHEN** a view's data-fetching operation fails
- **THEN** the system shows that view's error reporting rather than the empty-state component
