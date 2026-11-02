## ADDED Requirements

### Requirement: Admin can toggle the badge print flow
The system SHALL show a Badge print flow toggle to users with `tenants:update`, initialised from `badgePrintFlowEnabled` on `GET /tenants/me`, and SHALL save changes with `PATCH /tenants/me/settings` and body `{ "badgePrintFlowEnabled": boolean }`.

#### Scenario: Enable
- **WHEN** an authorised admin turns the toggle on and saves
- **THEN** the PATCH is sent with `true` and the Reception Badge printing entry becomes available

#### Scenario: Not authorised
- **WHEN** the user lacks `tenants:update`
- **THEN** the toggle is not shown

#### Scenario: Save failure
- **WHEN** the PATCH fails
- **THEN** the toggle reverts and the error message is shown

#### Scenario: Server flag off
- **WHEN** the server-level flag is off
- **THEN** the setting can still be saved but the flow stays unavailable, and the UI notes it may not take effect until enabled server-side
