## 1. Data model and migration

- [x] 1.1 Create `src/vmss_api/devices/` (`__init__`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `deps.py`, `tests.py`) with the `Device` model and partial unique index on `device_id`
- [x] 1.2 Add `check_in_device_id` / `check_out_device_id` FKs (indexed) to `invitations/models.py`
- [x] 1.3 Add `TenantSettings` model (single row, `enforce_kiosk_location_validation` default true) with repository
- [x] 1.4 Write one additive tenant Alembic revision (merge-head aware): `devices`, `tenant_settings`, invitation FKs; verify upgrade/downgrade
- [x] 1.5 Add `devices:view|manage|approve` (and `settings:view|manage` if absent) to `auth/rbac_catalog.py`; propagate to existing tenants' Admin role as earlier permission additions were

## 2. Device admin API

- [x] 2.1 Schemas: `DeviceRegister`, `DeviceOut` (with `branchName`, `buildingName`, `canApprove/canEnable/canDisable`), enums `ApprovalStatus`/`OperatingMode`, sort whitelist
- [x] 2.2 Repository: joined branch/building load, filters (`approvalStatus`, `status`, `operatingMode`, `branchId`, `buildingId`), `device_id` lookup
- [x] 2.3 Service: branch/building validation (active, building∈branch), approve/enable/disable with pending → 409 guard and idempotent repeats, soft delete
- [x] 2.4 Router: `GET /devices`, `GET /devices/{id}`, `POST /{id}/approve|enable|disable`, `DELETE /{id}` with permissions, `response_model`, audit actions; register in `api.py` and `_TAGS_METADATA`

## 3. Public device registration

- [x] 3.1 `POST /api/v1/devices/register` (declared before `/{id}` routes): default-tenant resolution, per-IP rate limit, no bearer token
- [x] 3.2 Upsert by `device_id` (create pending/inactive → 201; existing → current status, no mutation → 200); audit `device_registered` with null actor

## 4. Device traceability on check-in/out

- [x] 4.1 `devices/deps.py::resolve_checkin_device` reading `device-id`; 403 for unknown/pending/disabled; `None` when absent
- [x] 4.2 Wire into tracking-ID check-in, QR check-in/out (v2) and staff check-out (v1); document the header in OpenAPI
- [x] 4.3 Persist check-in/out device in `invitations/service.py` only on real state change; clear check-out device on re-entry; add `device_id` to audit entries
- [x] 4.4 Add `checkInDevice`/`checkOutDevice` to invitation detail and check-in/out responses with eager loading

## 5. Location validation and admin toggle

- [x] 5.1 Branch/building mismatch check in check-in service paths before state change; 422 messages naming branch vs building
- [x] 5.2 `GET/PUT` endpoint for `enforceKioskLocationValidation` with permissions, audit, `response_model`; register router and tag
- [x] 5.3 Read the setting once per check-in request; default true when no row exists

## 6. Tests and docs

- [x] 6.1 Device tests: registration (new, idempotent, bad building, bad mode, rate limit), approve/enable/disable matrix incl. 409 on pending, filters, delete, permission-denied, tenant isolation
- [x] 6.2 Invitation tests: valid/unknown/pending/disabled device, no-header compatibility, idempotent repeat does not overwrite, re-entry, Idempotency-Key replay
- [x] 6.3 Location-validation tests: branch mismatch, building mismatch, no-building invitation, setting off, setting permission-denied, setting tenant isolation
- [x] 6.4 Add `docs/features/devices.md`, update `registrations.md`; run `ruff check`, `ruff format --check`, mypy on touched `core/`/`auth/` code, full `pytest`, and `test_api_documentation.py`
