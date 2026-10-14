## Why

The backend now supports registered, admin-approved devices (kiosks and security gates) and records which device performed each check-in/out. The admin UI still manages reception desks and security gates as plain physical-location registers, so admins cannot approve, enable, or disable devices, cannot control kiosk location validation, and cannot see which device handled a visit.

## What Changes

- **BREAKING (UI)**: The Reception Desks (`/admin/reception-desks`) and Security Gates (`/admin/security-gates`) lists switch from the legacy desk/gate registers to the device list (`GET /api/v1/devices`, filtered by `operatingMode=kiosk` and `operatingMode=security` respectively). The legacy Add/Edit forms, their routes, and their delete/filter behavior are removed from these pages. `/api/v1/kiosks` and the Kiosks page are untouched.
- Device list: status filter (Pending Approval / Approved / Disabled mapped to `approvalStatus` + `status`), branch and building filters, paging and sorting; row actions Approve, Enable, Disable, Delete shown per the server-provided `canApprove` / `canEnable` / `canDisable` flags.
- New admin setting "Enforce kiosk location validation" (GET/PUT `/admin/settings/kiosk-location-validation`, default on), shown in the admin area and gated by `settings:view` / `settings:manage`.
- Add `devices:view`, `devices:manage`, `devices:approve`, `settings:view`, `settings:manage` to the role/permission UI and gate the new pages/actions on them.
- Invitation detail displays `checkInDevice` / `checkOutDevice` (name, operating mode, device id) when present.
- Out of scope (mobile-only, documented for the contract): `POST /devices/register`, the `device-id` header on check-in/check-out, and the 403 "device not approved" / 422 location-mismatch handling for those mobile calls. If a web flow later sends `device-id`, it must surface those errors as-is.

## Capabilities

### New Capabilities
- `admin-devices`: device list, filters, approval/enable/disable/delete actions, and permission gating shared by the Reception Desks and Security Gates pages.
- `admin-kiosk-location-validation`: admin setting to enforce kiosk check-in location validation.

### Modified Capabilities
- `admin-reception-desks`: page now lists kiosk devices instead of legacy desks.
- `admin-security-gates`: page now lists security devices instead of legacy gates.
- `admin-invitations`: invitation detail shows the check-in/check-out device.

## Impact

- `src/data/api/api-endpoints.ts`: new device and setting endpoints.
- `src/domain/entities/`: new device and setting Zod schemas; invitation-detail schema gains `checkInDevice` / `checkOutDevice`.
- `src/data/repositories/`, `src/data/use-cases/`, `src/infrastructure/`, `src/composition-root.ts`: new device and setting ports/adapters/use cases wired into `AppDependencies`; legacy desk/gate repositories, use cases, and forms removed.
- `src/presentation/pages/admin-reception-desks`, `admin-security-gates`, `admin-organisation-configs` (or settings host), `AdminSidebar`, `App.tsx` routes, `VisitorInfoModal`, role permission UI.
- Depends on backend `docs/features/devices.md`; new permissions are migrated into existing Admin roles by the backend.
