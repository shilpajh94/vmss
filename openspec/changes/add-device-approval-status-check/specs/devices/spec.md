## ADDED Requirements

### Requirement: Public Device Approval Status Lookup
The system SHALL expose a public, rate-limited, bearer-token-free `GET /api/v1/devices/approval-status` taking a required `deviceId` query parameter (1–255 chars). The tenant SHALL be resolved server-side, never from the request. For a live (non-deleted) device the response SHALL be 200 with `deviceId`, `operatingMode` (`kiosk` | `security`), `approvalStatus` (`pending` | `approved`), `isActive`, and `approved`, where `approved` is true only when `approvalStatus=approved` and `isActive=true`. The endpoint SHALL NOT create, modify, or approve any device, and SHALL NOT expose name, branch, building, or approver details. An unknown or soft-deleted `deviceId` SHALL return 404.

#### Scenario: Pending device
- **WHEN** a caller requests the status of a device that is registered but not yet approved
- **THEN** the response is 200 with `approvalStatus=pending`, `isActive=false`, `approved=false`

#### Scenario: Approved and enabled device
- **WHEN** a caller requests the status of an approved device that is enabled
- **THEN** the response is 200 with `approvalStatus=approved`, `isActive=true`, `approved=true`

#### Scenario: Approved but disabled device
- **WHEN** a caller requests the status of an approved device that an admin has disabled
- **THEN** the response is 200 with `approvalStatus=approved`, `isActive=false`, `approved=false`

#### Scenario: Unknown device
- **WHEN** the `deviceId` matches no live device
- **THEN** the response is 404 and no record is created

#### Scenario: Missing or empty deviceId
- **WHEN** `deviceId` is absent or empty
- **THEN** the request is rejected with 422

#### Scenario: Lookup is rate limited
- **WHEN** a caller exceeds the per-IP limit
- **THEN** the response is 429
