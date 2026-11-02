## ADDED Requirements

### Requirement: Badge Print Flow Setting
`settings.badge_print_flow_enabled` SHALL be read from `BADGE_PRINT_FLOW_ENABLED`, default `false`. It SHALL be present in `.env.example` with a safe value and documented in `docs/features/configuration.md`.

#### Scenario: Unset defaults to off
- **WHEN** the variable is not set
- **THEN** `settings.badge_print_flow_enabled` is `false`
