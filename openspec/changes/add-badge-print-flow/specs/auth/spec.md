## ADDED Requirements

### Requirement: Badge Printing Permissions
The permission catalog SHALL include `visitors:print_badge` and `tenants:update`. `visitors:print_badge` SHALL be granted to Reception and Admin. `tenants:update` SHALL be granted to Admin. Existing tenants' roles SHALL receive these grants through a tenant migration.

#### Scenario: Reception can print
- **WHEN** a Reception user's permissions are resolved
- **THEN** `visitors:print_badge` is present

#### Scenario: Security cannot print
- **WHEN** a Security user's permissions are resolved
- **THEN** `visitors:print_badge` is absent
