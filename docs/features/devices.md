# Devices (kiosk and security-gate registration)

Kiosk and security-gate devices register themselves from the mobile app, wait for
an admin to approve them, and are then traceable on every check-in/check-out.
Tenant-scoped (`devices` table in the tenant's own schema). **Unrelated to the
admin-managed `kiosks` list** (`kiosks.md`) and to the walk-in `X-Device-Key`
credential (`registrations.md`) — neither is read or changed by this feature.

## Lifecycle

`register` → `pending` (disabled) → admin `approve` → `approved` + enabled ⇄ `disable`/`enable`.
`enable`/`disable` return 409 while a device is `pending`. "Disabled" is
`approvalStatus=approved` with `isActive=false`; there is no stored third status.

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/v1/devices/register` | none, 10/minute per IP | Body: `name`, `deviceId`, `branchId`, optional `buildingId`, `operatingMode` (`kiosk`/`security`). Tenant comes from the server's default tenant, never the body. 201 when created (pending, disabled); 200 with the current status when the `deviceId` already exists — an existing record is never changed (a device can't relocate itself). `buildingId` must belong to `branchId`. |
| GET | `/api/v1/devices/approval-status?deviceId=<id>` | none, 60/minute per IP | Read-only status check for the mobile app. 200 `{deviceId, operatingMode, approvalStatus, isActive, approved}` where `approved` = approved **and** enabled (a disabled device is `approvalStatus=approved`, `approved=false`). 404 for an unknown or deleted `deviceId`; never creates or changes a device. Name/branch/approver are not exposed. |
| GET | `/api/v1/devices` | `devices:view` | Paginated. Filters: `approvalStatus`, `status` (`active`/`inactive`), `operatingMode`, `branchId`, `buildingId`; `sortBy` (`name`/`created_at`/`approval_status`), `sortOrder`. One list backs both admin pages: Reception Desks = `operatingMode=kiosk`, Security Gates = `operatingMode=security`. Each row has `branchName`, `buildingName`, `canApprove`/`canEnable`/`canDisable`. |
| GET | `/api/v1/devices/{id}` | `devices:view` | |
| POST | `/api/v1/devices/{id}/approve` | `devices:approve` | Sets approved + enabled; records approver and time. Repeat is a no-op 200. |
| POST | `/api/v1/devices/{id}/enable`, `/disable` | `devices:manage` | 409 until approved; repeat is a 200 no-op. |
| DELETE | `/api/v1/devices/{id}` | `devices:manage` | 204, soft delete; the `deviceId` can register again. |
| GET / PUT | `/api/v1/admin/settings/kiosk-location-validation` | `settings:view` / `settings:manage` | Body/response `{"enforceKioskLocationValidation": bool}`. Defaults to `true`. |

Audit actions: `device_registered`, `device_approved`, `device_enabled`,
`device_disabled`, `device_deleted`, `kiosk_location_validation_updated`.

## `device-id` on check-in / check-out

`PATCH /api/v2/invitations/{trackingId}/check-in`,
`PATCH /api/v2/invitations/qr/{token}/check-in`, `.../qr/{token}/check-out`, and
`PATCH /api/v1/invitations/{id}/check-out` accept an optional `device-id` header.

- Absent: behaves exactly as before; no device recorded, no location check.
- Present: must name a live, approved, enabled device, else **403** with no state
  change (unknown, pending and disabled share one message).
- The device is stored as `checkInDevice` / `checkOutDevice` on the invitation and
  returned in those responses and in the audit entry. Only a real state change
  writes it — a repeat check-in while already checked in does not overwrite it;
  re-entry after a check-out records the new device and clears `checkOutDevice`.

`device-id` is an identifier, not a credential: it can be replayed by anything
that knows it, so this is traceability, not authentication. A per-device secret
is a recommended follow-up.

## Branch / building validation

On **check-in** only, with `enforceKioskLocationValidation` on and a `device-id`
present: the device's branch must equal the invitation's, and — if the invitation
has a building — the device's building must equal it. Mismatch → **422** naming
branch or building, nothing changes. With the setting off, check-in proceeds and
the device is still recorded. Check-out is never validated.

## Rollout

Apply tenant migration `f2a4c6e8b0d1` to every tenant schema (creates `devices`
and `tenant_settings`, adds `invitations.check_in_device_id` /
`check_out_device_id`, and grants the new `devices:*` / `settings:*` permissions
to each tenant's `admin` role). Purely additive; no backfill. New tenants get the
permissions from the seeded catalog. Note the setting defaults to **on**, but it
only takes effect for requests that send `device-id`.
