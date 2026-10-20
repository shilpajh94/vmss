## ADDED Requirements

### Requirement: Code Check-In and Check-Out Accept and Persist a Device Id
The public code endpoints `PATCH /api/v2/invitations/code/check-in` and `PATCH /api/v2/invitations/code/check-out` SHALL accept an optional `device-id` header with the semantics defined by the `devices` capability and applied to the QR check-in/check-out endpoints. When a valid device is supplied, it SHALL be recorded as the invitation's check-in or check-out device, and the response SHALL expose it as `checkInDevice` / `checkOutDevice`.

#### Scenario: Code check-in records the device
- **WHEN** a visitor checks in by code with a valid, approved, enabled `device-id`
- **THEN** the invitation becomes `checked_in` and the response's `checkInDevice` identifies that device

#### Scenario: Code check-out records the device
- **WHEN** a checked-in visitor checks out by code with a valid `device-id`
- **THEN** the response's `checkOutDevice` identifies that device and `checkInDevice` is retained

#### Scenario: Header omitted
- **WHEN** either endpoint is called without `device-id`
- **THEN** the behavior is unchanged and `checkInDevice` / `checkOutDevice` are null as applicable

#### Scenario: Unusable device rejected
- **WHEN** the `device-id` is unknown, not approved, or disabled
- **THEN** the request is rejected with the same error as the QR endpoints and the invitation state is unchanged

#### Scenario: Location mismatch rejected
- **WHEN** location validation is enabled and the device's branch/building does not match the invitation
- **THEN** the code check-in is rejected exactly as the QR check-in is, leaving `checkInStatus` and `checkInDevice` unchanged

#### Scenario: Idempotent repeat does not overwrite
- **WHEN** a second code check-in from a different valid device arrives while already `checked_in`
- **THEN** the call is a 200 no-op and `checkInDevice` still shows the first device
