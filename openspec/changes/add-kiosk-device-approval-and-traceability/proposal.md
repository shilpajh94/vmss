## Why

Kiosks and security-gate devices have no onboarding control and no traceability: nothing records which device performed a check-in or check-out, any device can call the public check-in endpoints, and a kiosk in one building can check in a visit booked for another. The existing `kiosks` table (admin CRUD from `add-kiosk-admin-crud`) is a standalone name/description list with no device identity or check-in link, so it is left untouched and a new device model is introduced instead.

## What Changes

- New tenant-scoped `devices` table (new `devices/` feature package): `device_id` (unique per tenant), `name`, `branch_id`, `building_id`, `operating_mode` (`kiosk` | `security`), `approval_status` (`pending` | `approved`), `is_active`, approval metadata, soft delete. The existing `kiosks` feature, table, endpoints and specs are **not modified**.
- New public **device registration** endpoint (mobile app, no bearer token, rate-limited) accepting `branch`, `building`, `operating_mode`, `device_id` (plus name). Registers the device as `pending`; idempotent per `device_id`.
- Admin API on `/api/v1/devices` backing both pages from one filterable list: Reception Desks = `operatingMode=kiosk`, Security Gates = `operatingMode=security`. Filters for approval status, enabled/disabled, branch, building. Actions: approve, enable, disable, delete. Enable/disable only after approval.
- Check-In and Check-Out APIs accept a `device-id` request header; the resolved device is stored on the transaction (check-in device and check-out device on the invitation, and in the audit entry).
- On check-in, when enforcement is on, the device's registered branch/building is compared with the invitation's; a mismatch returns a validation error and blocks check-in.
- New tenant-level admin setting `enforce_kiosk_location_validation` (get/update, permission-gated, audited) toggling that validation.

## Capabilities

### New Capabilities
- `devices`: device registration, approval lifecycle, admin listing/actions for Reception Desks and Security Gates views, check-in/out traceability, branch/building validation, and its admin toggle.

### Modified Capabilities
- `invitations`: check-in/check-out endpoints accept `device-id`, persist the device, and apply the optional location validation.

## Impact

- Code: new `src/vmss_api/devices/` (model, schemas, repository, service, router, deps, tests); `invitations/` (router, service, models, schemas); settings storage; `auth/rbac_catalog.py` (`devices:view`, `devices:manage`, `devices:approve`, settings permissions); `api.py`, `main.py` `_TAGS_METADATA`.
- DB: one tenant Alembic revision (new `devices`, `tenant_settings`, invitation device FKs). No backfill needed. No global-schema change.
- API: additive only under `/api/v1` and `/api/v2` (new optional `device-id` header and response fields). Docs: new `docs/features/devices.md`, update `registrations.md`.
