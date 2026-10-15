## Why

A kiosk/security device registers itself via `POST /devices/register` and then waits for an admin to approve it. Today the only way for the mobile app to learn the outcome is to call the register endpoint again with a full payload (name, branch, mode), which is a write-shaped call that can create a record. The app needs a read-only way to ask, by device ID, "has my registration been approved yet?".

## What Changes

- Add a public, rate-limited, bearer-token-free `GET /api/v1/devices/approval-status?deviceId=<id>` that returns the device's `operatingMode`, `approvalStatus`, `isActive`, and a derived `approved` flag.
- The endpoint is read-only: it never creates, updates, or approves a device, and returns 404 for an unknown (or soft-deleted) `deviceId`.
- Tenant is resolved server-side (default tenant), never from the request.
- Document the endpoint in `docs/features/` and OpenAPI; no schema or migration changes.

## Capabilities

### New Capabilities
- `devices`: adds the device approval-status lookup requirement. (The `devices` capability itself is introduced by the in-flight `add-kiosk-device-approval-and-traceability` change and is not yet in `openspec/specs/`; this delta adds one requirement alongside it.)

### Modified Capabilities

## Impact

- Code: `src/vmss_api/devices/` (`router.py`, `service.py`, `schemas.py`, `tests.py`); `docs/features/devices.md`.
- API: one new additive public endpoint under `/api/v1/devices`; no breaking changes.
- No DB migration, no new permissions, no new settings.
