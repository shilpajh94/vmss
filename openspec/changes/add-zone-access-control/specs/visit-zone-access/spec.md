## Purpose

The visit-zone-access capability lets staff choose which zones an individual visit may enter, makes the "no zones mapped" situation visible, and shows zone entry events in the visit timeline.

## ADDED Requirements

### Requirement: A visit's zone picker shows its current zones
The system SHALL show, on a visit's detail view, a zone section for users who hold `zones:view`, listing the zones currently mapped to the visit and letting the user choose from the zones of the visit's branch.

#### Scenario: Visit has mapped zones
- **WHEN** the user opens a visit that has zones mapped
- **THEN** the zone section shows those zones as selected

#### Scenario: User lacks `zones:view`
- **WHEN** a user without `zones:view` opens a visit
- **THEN** the zone section is not shown

#### Scenario: Zone feature off
- **WHEN** the zone list fetch returned 404
- **THEN** the zone section is not shown

### Requirement: Saving replaces the visit's whole zone set
The system SHALL let a user who holds `invitations:edit` save the picker's selection, and SHALL send the full selected set so that it replaces the previous mapping. The picker SHALL offer only zones of the visit's branch.

#### Scenario: Save selection
- **WHEN** the user selects zones and saves
- **THEN** the system sends the complete selected set, shows the saved set, and triggers a success notification

#### Scenario: Zone from another branch rejected
- **WHEN** the backend rejects the save with 422 because a zone is outside the visit's branch
- **THEN** the system keeps the user's selection, shows the error, and does not claim the save succeeded

#### Scenario: Read-only for users without edit permission
- **WHEN** a user with `zones:view` but without `invitations:edit` opens a visit
- **THEN** the zone section is shown read-only with no save action

### Requirement: Clearing the selection falls back to category defaults
The system SHALL let the user clear the visit's zones and SHALL explain that clearing makes the visit's category default zones apply.

#### Scenario: Clear all zones
- **WHEN** the user clears every selected zone and saves
- **THEN** the system sends an empty set and shows that the category defaults now apply

### Requirement: An unmapped visit is visibly denied everywhere
The system SHALL show a warning in the zone section when neither the visit nor its visitor category has any mapped zone, stating that every zone will be denied for this visit.

#### Scenario: No mapping anywhere
- **WHEN** the visit has no zones and its category has no default zones
- **THEN** the zone section shows a warning that every zone will be denied

#### Scenario: Category defaults exist
- **WHEN** the visit has no zones but its category has default zones
- **THEN** the zone section shows the category defaults as the effective zones and no denial warning

### Requirement: Reception sets zones after creating or registering a visit
The system SHALL NOT send zones in the invitation-create request. After a visit is created or registered through the staff registration flow, the system SHALL offer the zone picker for the new visit and, when the user chooses zones, save them with a separate request.

#### Scenario: Zones chosen after registration
- **WHEN** a staff member registers a visit and chooses zones in the follow-up step
- **THEN** the system saves them for the newly created visit after the visit exists

#### Scenario: Zone save fails after the visit is created
- **WHEN** the visit is created but the follow-up zone save fails
- **THEN** the system tells the user the visit exists, shows the zone error, and lets them retry from the visit's detail view

### Requirement: Zone events appear in the visit timeline
The system SHALL show `zone_entered`, `zone_exited`, and `zone_entry_denied` events in the visit timeline with a distinct label and icon for each, and SHALL keep rendering any other unknown event type as a generic event.

#### Scenario: Zone entered
- **WHEN** a visit's timeline contains a `zone_entered` event
- **THEN** the timeline shows it with the "Entered zone" label and its summary

#### Scenario: Zone exited
- **WHEN** a visit's timeline contains a `zone_exited` event
- **THEN** the timeline shows it with the "Exited zone" label and its summary

#### Scenario: Zone entry denied
- **WHEN** a visit's timeline contains a `zone_entry_denied` event
- **THEN** the timeline shows it with a warning-styled "Zone entry denied" label and its summary
