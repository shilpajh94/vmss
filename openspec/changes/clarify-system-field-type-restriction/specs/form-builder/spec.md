## ADDED Requirements

### Requirement: The Field Properties Panel Explains Why a System Field's Type Cannot Be Changed
When the Field Type control is disabled because a field is system-seeded
(`isSystem: true`, whether locked or toggleable), the Field Properties
panel SHALL show inline text explaining that the field's type is fixed
because it's a default system field, rather than leaving the disabled
control with no explanation.

#### Scenario: Admin opens a toggleable system field's properties
- **WHEN** an admin opens the Field Properties panel for a system-seeded
  field that is not locked (e.g. "ID Proof Type")
- **THEN** the Field Type control is disabled and inline text explains
  that its type is fixed because it's a default system field

#### Scenario: Admin opens a locked field's properties
- **WHEN** an admin opens the Field Properties panel for a locked field
- **THEN** the Field Type control is disabled and shows the same
  explanatory text, consistent with a toggleable system field

#### Scenario: Admin opens an admin-authored field's properties
- **WHEN** an admin opens the Field Properties panel for a non-system,
  admin-authored field
- **THEN** the Field Type control is enabled and no explanatory text about
  a fixed type renders
