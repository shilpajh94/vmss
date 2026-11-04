## ADDED Requirements

### Requirement: Required Kiosk Device Resolution
The system SHALL provide a dependency that resolves a `device-id` header as a **required** kiosk device: the device must be approved, enabled, not deleted and have `operating_mode = kiosk`. Failure SHALL use the same `403` response as the existing optional resolution. The existing optional `device-id` behaviour on check-in/out endpoints SHALL be unchanged.

#### Scenario: Kiosk device accepted
- **WHEN** the header names an approved, enabled `kiosk` device
- **THEN** the device is returned to the route

#### Scenario: Security-mode device rejected for kiosk routes
- **WHEN** the header names an approved `security` device
- **THEN** the response is `403`

#### Scenario: Existing optional usage unchanged
- **WHEN** an existing check-in endpoint receives no `device-id`
- **THEN** it still proceeds without a device
