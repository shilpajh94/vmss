## Purpose

The emergency-inside-by-zone capability shows staff, during an emergency, everyone currently inside the premises grouped by the zone they are in, so that none are missed.

## ADDED Requirements

### Requirement: Inside report requires `emergency:view`
The system SHALL show the inside-by-zone entry and page only to signed-in users who hold `emergency:view`, and SHALL hide them when the zone feature is off.

#### Scenario: User lacks `emergency:view`
- **WHEN** a signed-in user without `emergency:view` opens the portal
- **THEN** no inside-by-zone entry is shown and its route is not rendered for them

#### Scenario: Zone feature off
- **WHEN** the zone list fetch returned 404
- **THEN** no inside-by-zone entry is shown

### Requirement: Visitors inside are grouped by zone
The system SHALL load the full inside report in one request (it is not paginated) and show one group per zone with the zone name and the visitors inside it. Each visitor row SHALL show the visitor name, host name, badge number, and time entered. The system SHALL show visitors without a zone in a separate "Not in a zone" group and SHALL show the total number inside.

#### Scenario: Report loads
- **WHEN** the page loads and the request succeeds
- **THEN** it shows each zone with its visitors, the "Not in a zone" group, and the total inside

#### Scenario: Nobody inside
- **WHEN** the report has a total of zero
- **THEN** the system shows the shared empty-state component

#### Scenario: Load failure
- **WHEN** the request fails
- **THEN** the system shows an error message and allows retrying without reloading the page

#### Scenario: Branch scoping
- **WHEN** a branch is selected
- **THEN** the report shows only the zones of that branch

### Requirement: The report can be refreshed and is complete
The system SHALL let the user refresh the report on demand, SHALL show when it was last loaded, and SHALL NOT truncate the list.

#### Scenario: Manual refresh
- **WHEN** the user activates refresh
- **THEN** the system reloads the report and updates the last-loaded time

#### Scenario: Large report
- **WHEN** the report contains many visitors
- **THEN** every visitor is reachable on the page
