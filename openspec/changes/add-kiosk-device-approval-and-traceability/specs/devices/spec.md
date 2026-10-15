## ADDED Requirements

### Requirement: Device Record
The system SHALL store a tenant-scoped `Device` with `name` (required, max 255), `deviceId` (required, max 255, unique among non-deleted devices), `branchId` (required), `buildingId` (optional), `operatingMode` (`kiosk` | `security`), `approvalStatus` (`pending` | `approved`), `isActive`, `approvedAt`/`approvedByUserId`, and soft-delete via `deleted_at`. `buildingId` MUST belong to `branchId`; both MUST be active. This record is independent of the existing `kiosks` records, which are unchanged.

#### Scenario: Deleted device's id is reusable
- **WHEN** a device is soft-deleted and another device registers with the same `deviceId`
- **THEN** the registration succeeds as a new pending device

#### Scenario: Building does not belong to branch
- **WHEN** a payload's `buildingId` is not a building of `branchId`
- **THEN** the request is rejected with 422

### Requirement: Public Device Registration Creates a Pending Device
The system SHALL expose a public, rate-limited, bearer-token-free `POST /api/v1/devices/register` accepting `name`, `deviceId`, `branchId`, `buildingId`, and `operatingMode`. The tenant SHALL be resolved server-side, never from the payload. A new registration SHALL be stored `approvalStatus=pending`, `isActive=false`. Registering a `deviceId` that already has a live record SHALL NOT create a second record, SHALL NOT alter its stored location or mode, and SHALL return its current `approvalStatus`.

#### Scenario: New device registers
- **WHEN** a device POSTs a valid payload with an unused `deviceId`
- **THEN** a pending, disabled device is created and returned with 201

#### Scenario: Re-registration is idempotent
- **WHEN** a device re-registers an existing live `deviceId`, possibly with different branch/building/mode
- **THEN** no record is created, stored values are unchanged, and the current status is returned with 200

#### Scenario: Invalid operating mode
- **WHEN** `operatingMode` is neither `kiosk` nor `security`
- **THEN** the request is rejected with 422

#### Scenario: Registration is rate limited
- **WHEN** a caller exceeds the per-IP limit
- **THEN** the response is 429

### Requirement: Device Listing With Filters
The system SHALL list devices (`devices:view`) with `page`/`pageSize` pagination, whitelisted `sortBy`/`sortOrder` (`name`, `created_at`, `approval_status`), and typed filters `approvalStatus`, `status` (`active`/`inactive`), `operatingMode`, `branchId`, `buildingId`, excluding soft-deleted devices. Each item SHALL include `branchName` and `buildingName` resolved without per-row queries, and `canApprove`/`canEnable`/`canDisable` flags. One list serves Reception Desks (`operatingMode=kiosk`) and Security Gates (`operatingMode=security`); there is no separate pending list.

#### Scenario: Pending filter
- **WHEN** the caller passes `approvalStatus=pending`
- **THEN** only devices awaiting approval are returned

#### Scenario: Mode filter drives each page
- **WHEN** the caller passes `operatingMode=security`
- **THEN** only security devices are returned; `operatingMode=kiosk` returns only reception kiosks

#### Scenario: Disabled filter
- **WHEN** the caller passes `approvalStatus=approved&status=inactive`
- **THEN** only approved-but-disabled devices are returned

#### Scenario: Action flags
- **WHEN** a pending device is listed
- **THEN** `canApprove=true`, `canEnable=false`, `canDisable=false`; for an approved enabled device `canDisable=true` and the other two are false

#### Scenario: Invalid sort column
- **WHEN** `sortBy` is not in the whitelist
- **THEN** the request is rejected with 422

### Requirement: Approve, Enable, Disable, and Delete Devices
The system SHALL provide `POST /api/v1/devices/{id}/approve` (`devices:approve`), `POST /{id}/enable`, `POST /{id}/disable`, and `DELETE /{id}` (`devices:manage`). Approval sets `approvalStatus=approved`, `isActive=true`, `approvedAt`, `approvedByUserId`; approving an approved device is a no-op 200. Enable and disable SHALL return 409 while the device is `pending`; repeating them is an idempotent 200 with no duplicate audit entry. Delete is a soft delete returning 204. Each action SHALL be audited via background task (`device_approved|enabled|disabled|deleted`).

#### Scenario: Approve, disable, enable
- **WHEN** an admin approves a pending device, disables it, then enables it
- **THEN** `isActive` is `true`, `false`, `true` and `approvalStatus=approved` throughout

#### Scenario: Enable a pending device
- **WHEN** an admin enables or disables a pending device
- **THEN** the response is 409 and the device is unchanged

#### Scenario: Approve without permission
- **WHEN** a caller lacking `devices:approve` approves a device
- **THEN** the response is 403

#### Scenario: Delete
- **WHEN** an admin deletes a device
- **THEN** the response is 204, the row keeps `deleted_at`, and it no longer lists or authorizes check-ins

#### Scenario: Tenant isolation
- **WHEN** a device exists in tenant A
- **THEN** it is never visible to tenant B

### Requirement: Check-In and Check-Out Record the Originating Device
Every check-in and check-out endpoint (staff, tracking-ID, QR) SHALL accept an optional `device-id` header. When present it MUST resolve to a live, approved, enabled device of the resolved tenant; the device SHALL be stored on the transaction (separately for check-in and check-out) and included in the audit entry. When absent, the transaction proceeds as today with no device recorded and no location validation. An unknown, pending, or disabled `device-id` SHALL be rejected with 403 and no state change.

#### Scenario: Check-in with a valid device
- **WHEN** a check-in carries the `device-id` of an approved, enabled device
- **THEN** the invitation is checked in and that device is stored as its check-in device

#### Scenario: Check-out with a valid device
- **WHEN** a check-out carries a valid `device-id`
- **THEN** the device is stored as the check-out device and the check-in device is unchanged

#### Scenario: Unknown, pending or disabled device
- **WHEN** the header names an unknown, pending, or disabled device
- **THEN** the response is 403 and nothing changes

#### Scenario: No device header
- **WHEN** a check-in has no `device-id`
- **THEN** it behaves as before and no device is recorded

### Requirement: Check-In Validates Device Branch and Building
When `enforceKioskLocationValidation` is on and a device is identified, check-in SHALL compare the device's branch with the invitation's branch and, when the invitation has a building, the device's building with the invitation's. On mismatch the system SHALL reject with 422 and a message naming branch or building, with no state change. When off, mismatches SHALL NOT block check-in. Check-out is not validated.

#### Scenario: Branch mismatch, enforcement on
- **WHEN** the device's branch differs from the invitation's
- **THEN** check-in is rejected with 422 and a branch-mismatch message

#### Scenario: Building mismatch, enforcement on
- **WHEN** branches match, the invitation has a building, and the device's building differs
- **THEN** check-in is rejected with 422 and a building-mismatch message

#### Scenario: Mismatch, enforcement off
- **WHEN** enforcement is off and locations differ
- **THEN** check-in succeeds and the device is still recorded

#### Scenario: Matching location
- **WHEN** enforcement is on and branch and building match
- **THEN** check-in proceeds

### Requirement: Location Validation Is Admin-Configurable
The system SHALL provide permission-gated endpoints to read and update a tenant-level boolean `enforceKioskLocationValidation`, defaulting to `true`. Updates SHALL be audited; reads require a settings view permission and writes a settings manage permission.

#### Scenario: Admin disables enforcement
- **WHEN** a caller with the write permission sets it to `false`
- **THEN** it is persisted, audited, and mismatched check-ins are no longer blocked

#### Scenario: Missing permission
- **WHEN** a caller lacking the write permission updates it
- **THEN** the response is 403

#### Scenario: Tenant isolation
- **WHEN** tenant A changes the setting
- **THEN** tenant B's value is unaffected
