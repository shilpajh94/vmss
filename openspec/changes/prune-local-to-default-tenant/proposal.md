## Why

The Export invitations dialog on the local portal fails with "You do not
have permission to perform this action". The local database has two
tenants:
- `default`, the one the portal signs in to, and
- `boardqa`, an ad-hoc QA tenant created on 2026-10-12 for board testing.

During `add-invitation-export` QA, the new tenant migration (`4ea4f6ccffbd`,
which grants `invitations:export`) was applied to `boardqa` only. So
`tenant_default` is still on `6054f5200ed1`, and its Admin and Reception
roles don't hold the permission.

A second local tenant also adds risk without any benefit:
- Test fixes and migrations get checked against one tenant while the team
  uses the other.
- The daily rollup snapshot is sent for both tenants.
- Stray data sits in Redis and in local file storage.

The team's decision is that local environments run exactly **one tenant,
the default**, and all test and QA data lives in it. The default tenant
already holds a complete QA dataset (375 invitations across every status,
plus an Admin user and a Reception/Host user), so nothing has to be moved
across.

## What Changes

- **Fix the 403 now:** bring `tenant_default` to the current tenant
  migration head, re-sync its standard role grants, and confirm Admin and
  Reception hold `invitations:export`.
- **New dev script `scripts/prune_non_default_tenants.py`:** removes every
  tenant except the one named by `TENANT_DEFAULT_SLUG`. For each removed
  tenant it:
  - drops its Postgres schema;
  - deletes its rows from the global tables that reference a tenant
    (`tenant_user_index`, `tenant_schema_versions`,
    `registration_device_keys`, `platform_audit_events`) and its `tenants`
    row;
  - deletes its Redis keys (`vmss:<tenant_id>:*`) and its local storage
    folder.

  It never touches the default tenant or its data. Like
  `reset_dev_tenant_data.py`, it is a dry run unless `--yes` is passed. It
  refuses to run unless `APP_ENV` is `local` or `testing`, and also refuses
  if the default tenant doesn't exist, since that would mean deleting
  every tenant.
- **Run it once locally** to remove `boardqa`: its schema
  `tenant_boardqa`, 3 `tenant_user_index` rows, 1 `tenant_schema_versions`
  row, 5 Redis keys, and the `var/storage/vmss/<boardqa-id>/` folder.
- **Document the rule** in `docs/features/configuration.md`: a local
  environment has one tenant, local QA data is created in the default
  tenant, and any extra tenant created for an experiment is removed with
  the new script.

No API behaviour changes, no migrations, and production is unaffected.
There is no tenant-creating migration in either Alembic tree to remove;
`boardqa` was created by an ad-hoc script that was never committed.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `tenant-schema-maintenance`: adds a requirement that a local or testing
  environment can be pruned down to just its default tenant, safely and
  without touching the default tenant's data.

## Impact

- **Code:** a new `scripts/prune_non_default_tenants.py`, with tests for its
  core function against the real test database (default-tenant
  preservation, refusal guards, dry run).
- **Docs:** `docs/features/configuration.md`.
- **Local data:** the `boardqa` tenant and all its data are permanently
  deleted from the local DDEV database. The default tenant's data
  (`tenant_default`, its global rows, its storage and Redis keys) is
  unchanged.
- **Web QA notes:** the archived VMMS_WEB change
  `2026-10-12-board-sticky-headers-lazy-load/tasks.md` mentions the
  `boardqa` tenant. That is historical and left as is.
