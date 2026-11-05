## ADDED Requirements

### Requirement: Admin can choose whether badge printing requires ID verification
The system SHALL show a "Require ID verification before printing badge" toggle beside the "Enable badge printing" toggle to users with `tenants:update`, initialised from `badgePrintRequiresIdVerification` on `GET /tenants/me` (treated as `true` when the field is absent), and SHALL save changes with `PATCH /tenants/me/settings` and a body containing only `{ "badgePrintRequiresIdVerification": boolean }`.

#### Scenario: Default on
- **WHEN** the tenant response omits `badgePrintRequiresIdVerification`
- **THEN** the toggle shows as on

#### Scenario: Turn off
- **WHEN** an authorised admin turns the toggle off
- **THEN** the PATCH is sent with `false` and no other settings field

#### Scenario: Not authorised
- **WHEN** the user lacks `tenants:update`
- **THEN** the toggle is not shown

#### Scenario: Save failure
- **WHEN** the PATCH fails
- **THEN** the toggle reverts and the server's error message is shown

### Requirement: ID verification toggle applies only while badge printing is on
The system SHALL disable the ID verification toggle, with an explanation, while "Enable badge printing" is off, and SHALL NOT change the stored value merely because badge printing is toggled.

#### Scenario: Badge printing off
- **WHEN** "Enable badge printing" is off
- **THEN** the ID verification toggle is disabled and keeps its current value

#### Scenario: Badge printing turned on
- **WHEN** an admin turns "Enable badge printing" on
- **THEN** the ID verification toggle becomes interactive
