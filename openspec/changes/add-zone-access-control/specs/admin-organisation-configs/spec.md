## ADDED Requirements

### Requirement: Zone access control is switched on in Organisation Configs
The system SHALL show, on the Organisation Configs page, a "Zone Access Control" card with an on/off switch to users who hold `tenants:update`, reflecting the tenant's current setting, and SHALL hide the card from everyone else. Changing the switch SHALL save it to the tenant's settings.

#### Scenario: Setting loads
- **WHEN** an authorised user opens Organisation Configs
- **THEN** the card shows the tenant's current zone access setting

#### Scenario: Turned on
- **WHEN** the user turns the switch on and the save succeeds
- **THEN** the system shows a success notification and the zone screens become available without reloading the page

#### Scenario: Turned off
- **WHEN** the user turns the switch off and the save succeeds
- **THEN** the system shows a success notification and the zone screens are hidden

#### Scenario: Save fails
- **WHEN** the save request fails
- **THEN** the switch returns to its previous position and the system shows the server's message

#### Scenario: User lacks `tenants:update`
- **WHEN** a user without `tenants:update` opens Organisation Configs
- **THEN** the zone access card is not shown
