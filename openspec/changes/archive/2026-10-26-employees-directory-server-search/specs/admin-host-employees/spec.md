## ADDED Requirements

### Requirement: Employee list can be searched by name, email, or employee code
The system SHALL show a search box on the Employees page and SHALL narrow the employee list server-side to employees whose full name, email, or employee code contains the typed text (case-insensitive), sending the text as the `search` parameter of the employees list request. The system SHALL send the trimmed text only after typing has paused for about 300 ms, SHALL omit the parameter when the trimmed text is empty, SHALL limit the input to 255 characters, and SHALL return to the first page whenever the search text changes. Search SHALL combine with the Department, Role, and Status filters so that only employees matching all of them are shown, and the total and page count SHALL reflect the searched results.

#### Scenario: Search narrows the list
- **WHEN** an admin types "dina" into the search box and pauses
- **THEN** the table shows only employees whose name, email, or employee code contains "dina", ignoring case

#### Scenario: Typing does not request on every keystroke
- **WHEN** an admin types several characters in quick succession
- **THEN** the system sends a single list request after typing pauses, not one per keystroke

#### Scenario: Search resets to the first page
- **WHEN** an admin is on a later page and changes the search text
- **THEN** the list reloads from page 1

#### Scenario: Search combines with filters
- **WHEN** an admin has entered search text and selected a Department, Role, or Status filter
- **THEN** the table shows only employees matching the search and every selected filter

#### Scenario: Blank search behaves as no search
- **WHEN** the search box is empty or contains only whitespace
- **THEN** the list request carries no `search` parameter and the full (filtered) list is shown

#### Scenario: Pagination reflects search results
- **WHEN** a search matches fewer employees than a full page
- **THEN** the pagination controls reflect the reduced total

## MODIFIED Requirements

### Requirement: No filter matches shows a distinct empty state
The system SHALL, when one or more filters or a search are active and no employee matches them, show a message indicating no employees match the current search or filters, distinct from the message shown when the organisation has zero employees at all.

#### Scenario: No matches for active filters
- **WHEN** one or more filters are active and no employee matches them
- **THEN** the system shows a "no employees match" message instead of the zero-employees empty state

#### Scenario: No matches for search text
- **WHEN** search text is entered and no employee matches it
- **THEN** the system shows the "no employees match" message instead of the zero-employees empty state
