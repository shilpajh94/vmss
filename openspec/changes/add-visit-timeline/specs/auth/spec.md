## ADDED Requirements

### Requirement: Timeline Permission
The permission catalog SHALL include `timeline:view`, granted to Admin, Reception and Security. Existing tenants' roles SHALL receive the grant through a tenant migration.

#### Scenario: Reception can view timelines
- **WHEN** a Reception user's permissions are resolved
- **THEN** `timeline:view` is present

#### Scenario: Host cannot view timelines
- **WHEN** a Host user's permissions are resolved
- **THEN** `timeline:view` is absent
