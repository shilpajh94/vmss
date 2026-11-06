## ADDED Requirements

### Requirement: The branch default zone is shown as always allowed
The system SHALL show, in a visit's zone section, the visit's branch's active default zone as a locked "Always allowed" chip, in both editable and read-only modes. The chip SHALL NOT be selectable, SHALL NOT count as a selected zone, and SHALL NOT be sent in the saved zone set.

#### Scenario: Branch has a default zone
- **WHEN** the user opens a visit whose branch has an active default zone
- **THEN** the zone section shows that zone as an "Always allowed" chip that cannot be unticked

#### Scenario: Saving excludes the default
- **WHEN** the user saves the visit's zones
- **THEN** the request contains only the zones the user ticked, never the default zone

#### Scenario: Branch has no default zone
- **WHEN** the visit's branch has no active default zone
- **THEN** no "Always allowed" chip is shown and the section behaves as before

#### Scenario: Category zone section
- **WHEN** the zone section is for a visitor category
- **THEN** no "Always allowed" chip is shown

### Requirement: Denied-everywhere warning accounts for the default zone
The system SHALL show the "every zone will be denied" warning only when the visit has no effective zones and its branch has no active default zone. When the visit has no effective zones but the branch has a default, the system SHALL show a neutral notice that only the default zone is allowed.

#### Scenario: No zones, no default
- **WHEN** neither the visit nor its category maps a zone and the branch has no default
- **THEN** the warning that every zone is denied is shown

#### Scenario: No zones, default exists
- **WHEN** neither the visit nor its category maps a zone and the branch has an active default
- **THEN** the denied warning is not shown and the notice says only the default zone is allowed
