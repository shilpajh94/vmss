## Context

See proposal.md for why this change is needed. The current local state,
checked on 2026-10-14:

| | `default` | `boardqa` |
|---|---|---|
| Schema | `tenant_default`, revision `6054f5200ed1` (one behind head) | `tenant_boardqa`, revision `4ea4f6ccffbd` (head) |
| Data | 2 users, 375 invitations, 2 branches | 3 users, 370 invitations, 1 branch |
| `global.tenant_user_index` | 2 | 3 |
| `global.tenant_schema_versions` | 1 | 1 |
| `registration_device_keys` / `platform_audit_events` | 0 / – | 0 / 0 |
| Redis `vmss:<id>:*` | – | 5 keys (snapshot-sent markers, an idempotency key) |
| Files | – | `var/storage/vmss/<boardqa-id>/` |

Other facts that shape the design:
- No foreign key from any other schema points into `tenant_boardqa`.
- Neither Alembic tree contains a tenant-creating migration.
- `scripts/reset_dev_tenant_data.py` sets the house pattern for destructive
  dev scripts: refuse in production, dry run unless `--yes`, and
  default-tenant scoping from `settings.default_tenant_slug`.
- Local storage keys map to paths through `core/storage.py`: a key
  `vmss:{tenant_id}:...` becomes `storage_root/vmss/<tenant_id>/...`.

## Goals / Non-Goals

**Goals:**
- Fix the export 403 on the default tenant.
- Provide a repeatable, safe way to get back to "one tenant" after any
  local experiment.
- Remove `boardqa` without touching default-tenant data.

**Non-Goals:**
- Stopping the platform from creating tenants. Provisioning is a real
  product feature, and tests still create throwaway tenant schemas in the
  separate `vmss_test` database. This change is about the local *dev*
  database only.
- Moving `boardqa`'s QA data into the default tenant. The default tenant
  already has an equivalent dataset.
- Cleaning object storage in production-like backends. In this script,
  file removal is limited to the local disk backend.

## Decisions

### 1. Fix order: prune first, then upgrade
First run the prune script, then `scripts/upgrade_all_tenants.py`. Once
`boardqa` is gone, "all tenants" means only the default tenant, so the
upgrade's re-sync (role grants and form-builder defaults) runs only where
it should. The re-sync is additive: it grants missing catalog permissions,
leaves existing grants alone, and fills in form defaults only for a tenant
that has none. So it can't damage the default tenant's existing config.

*Alternative considered:* a targeted
`alembic -c alembic_tenant.ini -x tenant_schema=tenant_default upgrade head`.
That applies the migration but skips the `tenant_schema_versions` mirror
update and the grant re-sync, which is how the two tenants drifted apart
in the first place.

### 2. A reusable script, not a one-off SQL session
`scripts/prune_non_default_tenants.py` follows `reset_dev_tenant_data.py`:
- an `argparse` `--yes` flag,
- a `_run(confirmed)` coroutine, and
- the core `prune_non_default_tenants(db, redis, storage_root, *, confirmed)`
  extracted as a function, so tests can call it against the real test
  database.

A plain SQL cleanup would solve today's problem but leave no safe path for
the next time someone creates an experimental tenant.

### 3. Safety guards
- **Environment allow-list:** it runs only when `settings.environment` is
  `local`, `test` (what the pytest suite sets) or `testing`. That is stricter than the reset script's
  production-only deny-list, because dropping whole schemas is more
  destructive than truncating one.
- **The default tenant must exist** (looked up by
  `settings.default_tenant_slug`). Without it, "every non-default tenant"
  would mean every tenant.
- **Explicit keep:** the default tenant's id and schema name are compared
  explicitly before every drop or delete, rather than relying on a
  `WHERE id != ...` filter alone.
- **Schema names are checked before being used in DDL.** A name is quoted
  in `DROP SCHEMA` only if it is `settings.tenant_schema_prefix` followed
  by `[a-z0-9_-]`. Hyphens are legitimate, because slugs allow them. A name
  that doesn't match is reported and skipped, not dropped, so nothing can
  break out of the quoted identifier.

### 4. One transaction for the database, then Redis and files
All schema drops and global-row deletes run in one transaction:
- `DROP SCHEMA ... CASCADE` for each tenant schema,
- deletes from `tenant_user_index`, `tenant_schema_versions`,
  `registration_device_keys` and `platform_audit_events`,
- then the `tenants` rows.

Postgres DDL is transactional, so a failure rolls everything back. Redis
keys (removed with `SCAN` and `DEL` on `vmss:<tenant_id>:*`) and the local
storage folder are cleaned only after the commit succeeds. A crash between
the two steps leaves only harmless orphaned cache entries and files, never
a dangling database reference. The list of global tables lives in one
module-level tuple so it is easy to extend; it adds `tenant_schema_versions`
to the set the reset script uses.

### 5. Storage removal is local-disk only
Files are removed only when the local disk storage backend is in use. The
path is resolved through `core/storage.py`'s key-to-path mapping and must
sit under `settings.storage_root`. With any other backend, the script
reports that files were skipped.

### 6. A dry run prints a plan
For each tenant it would remove, the dry run prints: slug, id, schema,
global-row counts per table, Redis key count, and storage path with file
count. It exits non-zero without changing anything, the same as the reset
script.

### 7. Orphaned test leftovers are cleaned too
The first live run found 15,461 folders (412 MB) in `var/storage/vmss/`
and 46 Redis keys filed under tenant ids that match no `tenants` row. The
pytest suite writes into the same storage root and Redis as dev, using a
fresh tenant id per test. So after removing registered tenants, the
script also handles orphans:
- **Files:** it removes any `storage_root/vmss/<uuid>/` folder whose uuid
  isn't a remaining registered tenant.
- **Redis:** it removes any `vmss:<uuid>:*` key whose uuid isn't
  registered.

Only entries whose second segment parses as a UUID are considered, so
non-tenant keys and folders are never touched. Storing test files in a
temporary root, so this stops recurring, is a separate change
(`isolate-test-storage-and-cache`).

## Risks / Trade-offs

- [`boardqa`'s QA data is deleted permanently] → The user has asked for
  this, and the default tenant has an equivalent dataset. Before the
  confirmed run, take a `pg_dump` of the `tenant_boardqa` schema and its
  global rows into the scratchpad, as a short-lived safety net.
- [Someone runs the script against a shared dev database where a second
  tenant is wanted] → The environment allow-list, the dry-run default and
  the printed plan all guard against this, and the docs say when to use it.
- [Notes such as the board QA tenant memory and the archived web change
  refer to `boardqa`] → Update the local memory notes as part of applying;
  leave archived changes as historical record.

## Migration Plan

1. Back up `boardqa`: `pg_dump --schema=tenant_boardqa` plus a `COPY` of its
   global rows, saved to the scratchpad.
2. Dry run: `ddev exec uv run python scripts/prune_non_default_tenants.py`.
   Check that the plan lists only `boardqa`.
3. `... prune_non_default_tenants.py --yes`.
4. `ddev exec uv run python scripts/upgrade_all_tenants.py`. Confirm
   `tenant_default` is at head and Admin and Reception hold
   `invitations:export`.
5. Re-try the Export dialog as admin and as Reception on the default tenant.

**Rollback:** restore from the step 1 dump. There are no code-level
rollback concerns, because the script is additive tooling.
