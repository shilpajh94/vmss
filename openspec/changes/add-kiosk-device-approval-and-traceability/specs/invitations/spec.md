## ADDED Requirements

### Requirement: Check-In and Check-Out Endpoints Accept and Persist a Device Id
The tracking-ID check-in (`PATCH /api/v2/invitations/{trackingId}/check-in`), QR check-in and check-out (`/api/v2/invitations/qr/{token}/check-in|check-out`), and staff check-out (`PATCH /api/v1/invitations/{id}/check-out`) endpoints SHALL accept an optional `device-id` header with the semantics defined by the `devices` capability. The invitation SHALL expose `checkInDevice` and `checkOutDevice` (`{id, deviceId, name, operatingMode}` or null) in its detail and check-in/out responses. Because check-in may repeat (allow-multiple-checkins), `checkInDevice` SHALL reflect the device of the most recent state-changing check-in, and an idempotent repeat call while already checked in SHALL NOT overwrite it.

#### Scenario: Device shown in check-in response
- **WHEN** a visitor checks in with a valid `device-id`
- **THEN** the response's `checkInDevice` identifies that device

#### Scenario: Idempotent repeat does not overwrite
- **WHEN** a second check-in call from a different valid device arrives while already `checked_in`
- **THEN** the call is a 200 no-op and `checkInDevice` still shows the first device

#### Scenario: Re-entry after check-out records the new device
- **WHEN** a visitor checks out and checks in again from another device
- **THEN** `checkInDevice` shows the new device and `checkOutDevice` is cleared

#### Scenario: Rejected check-in leaves no trace
- **WHEN** a check-in is rejected for location mismatch
- **THEN** `checkInStatus` and `checkInDevice` are unchanged

#### Scenario: Idempotency-Key replay
- **WHEN** a request is replayed with the same `Idempotency-Key`
- **THEN** the cached response is returned and no second state change occurs (the `device-id` header is still validated on the replay)
