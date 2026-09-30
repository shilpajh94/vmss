## Why

Admins have no way to manage kiosks: the only kiosk-related record today is
`RegistrationDeviceKey`, a global-schema credential with no name, description,
or admin-facing lifecycle. The admin portal needs a first-class Kiosk record it
can add, edit, delete, and hide, modelled on how Branch is managed.

## What Changes

- New tenant-scoped `Kiosk` entity: `name`, `description`, `is_active`,
  `is_hidden`, soft delete (`deleted_at`), timestamps.
- New admin-only REST endpoints under `/api/v1/kiosks`: create, paginated list,
  get, update, hide/unhide, soft-delete.
- New permissions `kiosks:manage` and `kiosks:view`, added to the RBAC catalog
  (Admin gets both).
- "Hide" is an admin-list visibility flag: hidden kiosks are excluded from the
  default list and shown only when explicitly requested; a hidden kiosk is
  otherwise unaffected.
- New tenant migration for the `kiosks` table; audit-log entries for every
  mutation.
- Out of scope: linking a Kiosk to `RegistrationDeviceKey`, branch scoping, and
  any public/kiosk-facing endpoint.

## Capabilities

### New Capabilities
- `kiosks`: Admin CRUD, hide/unhide, and soft-delete of Kiosk records.

### Modified Capabilities

(none)

## Impact

- New package `src/vmss_api/kiosks/` (router, service, schemas, models,
  repository, tests) registered in `api.py`; tag added to `main.py`
  `_TAGS_METADATA`.
- `auth/rbac_catalog.py`: two new permission codes.
- New migration in `alembic_tenant/versions/` (must be applied to every
  tenant schema); `docs/features/kiosks.md`.
