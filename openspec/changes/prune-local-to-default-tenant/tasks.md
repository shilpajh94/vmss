## 1. Prune Script

- [x] 1.1 Create `scripts/prune_non_default_tenants.py`, modeled on `reset_dev_tenant_data.py`: module docstring with usage, `--yes` flag, `_run(confirmed)`, and an extracted `prune_non_default_tenants(db, redis, storage_root, *, confirmed)` that returns a per-tenant plan/result
- [x] 1.2 Add the guards:
  - `settings.environment` must be `local` or `testing`;
  - the default tenant (`settings.default_tenant_slug`) must exist;
  - its id and schema are excluded explicitly;
  - a schema name is used in DDL only if it matches `tenant_schema_prefix` plus the slug character set, otherwise it is reported and skipped.
- [x] 1.3 Dry run: print each tenant's slug, id, schema, row counts per global table (`tenant_user_index`, `tenant_schema_versions`, `registration_device_keys`, `platform_audit_events`), Redis key count, and storage path with file count. Exit non-zero with nothing changed.
- [x] 1.4 Confirmed run, in one transaction: `DROP SCHEMA "<schema>" CASCADE`, delete the global rows, then the `tenants` rows. After commit: `SCAN`/`DEL` `vmss:<tenant_id>:*` in Redis, and remove `storage_root/vmss/<tenant_id>/` (local backend only, path checked to sit under `storage_root`).
- [x] 1.5 Tests (real `vmss_test` database, factories) that call the core function:
  - an extra tenant is fully removed while the default tenant's schema rows, global rows, Redis keys and files are unchanged;
  - a dry run changes nothing;
  - the run refuses in `production`/`staging`;
  - the run refuses when the default tenant is missing;
  - it reports "nothing to remove" when only the default tenant exists.

## 2. Docs

- [x] 2.1 `docs/features/configuration.md`: add a "One tenant locally" note. Local QA data goes in the default tenant, and an extra tenant is removed with `prune_non_default_tenants.py` (dry run, then `--yes`) followed by `upgrade_all_tenants.py`. Also list `tenant_schema_versions` among the global tables the reset script description mentions, if the reset script is updated to match.

## 3. Apply to the Local Environment

- [x] 3.1 Back up `boardqa` to the scratchpad (`pg_dump --schema=tenant_boardqa`, plus its `global.tenants`, `tenant_user_index` and `tenant_schema_versions` rows)
- [x] 3.2 Run the prune script as a dry run and confirm the plan lists only `boardqa` (3 index rows, 1 version row, 5 Redis keys, one storage folder)
- [x] 3.3 Run it with `--yes`. Then confirm only `global` and `tenant_default` schemas remain, `global.tenants` has the single `default` row, and the default tenant's counts are unchanged (2 users, 375 invitations, 2 branches, 2 index rows).
- [x] 3.4 Run `scripts/upgrade_all_tenants.py`, then confirm `tenant_default` is on `4ea4f6ccffbd` and its `admin` and `reception` roles hold `invitations:export`
- [x] 3.5 Re-try the Export dialog on the default tenant as Admin and as Reception: the file downloads and there is no 403
- [x] 3.6 Update the local QA memory notes: retire the `boardqa` reference, and record that local QA uses the default tenant only

## 4. Verification

- [x] 4.1 `ruff check`, `ruff format --check` and `mypy` on the new script, plus `pytest` for the new tests (not in parallel with another pytest run)

## 5. Orphaned Test Leftovers

- [x] 5.1 Extend the script: after the registered-tenant removals, find `storage_root/vmss/<uuid>/` folders (local backend only) and `vmss:<uuid>:*` Redis keys whose uuid is not a remaining registered tenant. Report their counts on a dry run and remove them on `--yes`. Never touch the default tenant or entries not named by a UUID.
- [x] 5.2 Tests: orphaned folders and keys are removed on a confirmed run, kept on a dry run, and the default tenant's files and keys plus a non-UUID entry are untouched
- [x] 5.3 Run it locally (dry run, then `--yes`). Confirm only the default tenant's folder and keys remain under `vmss/`, and that the default snapshot is unchanged.
- [x] 5.4 Propose the follow-up change `isolate-test-storage-and-cache` (planning only), so test runs stop writing into dev storage and Redis

