## Why

`tenant_default` (and any other existing tenant) is missing the
`poc_user_id`/`poc_role_id`/`poc_name` columns that
`src/vmss_api/invitations/models.py` expects on `invitations`, causing a
500 (`UndefinedColumnError: column invitations.poc_user_id does not
exist`) on invitation creation. The root cause isn't a missing migration —
`alembic_tenant/versions/c1d8e5f9a2b3_invitation_point_of_contact.py`
exists and adds exactly those columns. The `alembic_tenant` tree has
diverged into **two unmerged heads** (`c1d8e5f9a2b3`, the POC-fields
migration, and `f1a2c7e9b3d5`, the form-builder migration), both branching
off the same parent `6f3a1c9d4e7b` with no merge revision authored. That
makes `command.upgrade(cfg, "head")` / `ScriptDirectory.get_current_head()`
raise `CommandError: Multiple head revisions are present`, so the
upgrade-all-tenants path (`platform/service.py::upgrade_all_tenant_schemas`)
cannot run at all, and the only drift detector
(`backend_pre_start.py::check_tenant_schema_drift`, per
`tenant-schema-maintenance` spec) merely logs a `WARNING` at startup rather
than failing loud — so this reached a live environment undetected. CI also
runs no `pytest`/`alembic heads` step that would have caught the
multi-head condition pre-merge.

## What Changes

- Author an Alembic merge revision unifying `c1d8e5f9a2b3` and
  `f1a2c7e9b3d5` into a single `alembic_tenant` head.
- Run the upgrade-all-tenants operation against every existing tenant
  schema (`tenant_default` at minimum) so the merged head — including the
  POC columns and the form-builder migration — is actually applied,
  clearing the current production error.
- Harden the tenant-schema drift check so a migration tree with more than
  one head is detected and reported as a distinct, higher-severity
  condition (not conflated with ordinary "tenant N revisions behind"
  lag), instead of the upgrade operation raising an unhandled
  `CommandError` or the startup check silently no-oping on it.
- Add a CI check (`alembic -c alembic_tenant.ini heads`, or equivalent)
  that fails the build when the tenant migration tree has more than one
  head, so a future migration authored against a stale `down_revision`
  is caught at review time instead of at runtime in a live tenant schema.

## Capabilities

### New Capabilities
_None._

### Modified Capabilities
- `tenant-schema-maintenance`: the existing "lagging behind head" drift
  requirement is extended to also cover the case where the migration tree
  itself has multiple heads — today an unrepresented, unhandled failure
  mode rather than a reported one.

## Impact

- `alembic_tenant/versions/` — new merge migration file.
- `src/vmss_api/platform/service.py` (`upgrade_tenant_schema`,
  `upgrade_all_tenant_schemas`, `get_tenant_migration_head`) and
  `src/vmss_api/backend_pre_start.py` (`check_tenant_schema_drift`) —
  multi-head detection/handling.
- Every existing tenant Postgres schema (currently just `tenant_default`)
  — gets migrated to the merged head via `scripts/upgrade_all_tenants.py`.
- CI pipeline config (`CI-CD/Azure-Pipeline-API-DEV.yml` or equivalent) —
  new guard step.
- No API contract or client-visible schema change beyond restoring the
  already-shipped POC fields to working order.
