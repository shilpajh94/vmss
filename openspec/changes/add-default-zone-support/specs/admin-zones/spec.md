## ADDED Requirements

### Requirement: A branch can have one default zone
The system SHALL let a user with `zones:manage` mark a zone as its branch's default zone using a "Default zone" toggle on the zone form, on create and edit, and SHALL send `isDefault` with the zone payload. The toggle SHALL explain that the default zone is always allowed for every visitor at the branch, that only one is allowed per branch, and that it still needs a linked gate.

#### Scenario: Make a zone the default
- **WHEN** the user turns on "Default zone" and saves
- **THEN** the system sends `isDefault: true`, and after saving the zone list shows that zone as the default and the branch's previous default no longer shows as default

#### Scenario: Clear the default
- **WHEN** the user turns off "Default zone" on the current default zone and saves
- **THEN** the system sends `isDefault: false` and the branch has no default zone

#### Scenario: Inactive zone cannot be made default
- **WHEN** the zone's status is Inactive
- **THEN** the "Default zone" toggle is disabled

#### Scenario: Backend rejects an inactive default
- **WHEN** the backend answers 422 to a save that sets `isDefault` on an inactive zone
- **THEN** the user stays on the form with their input and sees the error

#### Scenario: Backend predates the feature
- **WHEN** a zone response has no `isDefault`
- **THEN** the zone is treated as not default and the page renders without error

### Requirement: Zone list shows and filters the default
The system SHALL show a "Default" badge on each default zone in the zone list and SHALL offer a "Default zone" filter (All, Default, Not default) that sends `isDefault=true|false`.

#### Scenario: Default badge
- **WHEN** the list contains a default zone
- **THEN** its row shows a "Default" badge

#### Scenario: Filter to default zones
- **WHEN** the user filters by "Default"
- **THEN** the system requests `isDefault=true` and shows only default zones

### Requirement: Default zone protection errors are explained
The system SHALL show "Choose another default zone first." when deleting or deactivating the current default zone is rejected with 409, and SHALL prevent deactivating a zone whose "Default zone" toggle is on.

#### Scenario: Delete the default zone
- **WHEN** the user confirms deleting the current default zone and the backend answers 409
- **THEN** the system shows "Choose another default zone first." and the zone stays in the list

#### Scenario: Deactivate the default zone
- **WHEN** the user sets a default zone to Inactive and saves, and the backend answers 409
- **THEN** the system shows "Choose another default zone first." and keeps the form open

#### Scenario: No permission at the branch
- **WHEN** the backend answers 403 to a save that sets `isDefault`
- **THEN** the system shows an error and does not claim the save succeeded
