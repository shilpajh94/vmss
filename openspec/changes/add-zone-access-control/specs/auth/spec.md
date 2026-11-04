## ADDED Requirements

### Requirement: Zone Access Permissions
The system SHALL add permissions `zones:manage`, `zones:view`, `access:scan` and `emergency:view` to the catalog and grant them to default roles via a tenant migration for existing roles.

#### Scenario: Default grants
- **WHEN** a tenant is provisioned or migrated
- **THEN** Admin holds `zones:manage`; Admin, Reception, Security hold `zones:view` and `emergency:view`; Security holds `access:scan`

#### Scenario: Ungranted role
- **WHEN** a role lacking a permission calls the matching route
- **THEN** the response is 403 through the standard error envelope
