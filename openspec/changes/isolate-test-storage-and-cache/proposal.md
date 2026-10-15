## Why

The pytest suite writes uploaded files and Redis keys into the same
places the local dev environment uses: `./var/storage` and Redis database
0. Each test has a fresh tenant id, so every run leaves new folders and
keys under tenant ids that don't exist. By 2026-10-14 this had built up to
15,461 folders (412 MB) and 46 Redis keys, which `prune-local-to-default-tenant`
had to clean up.

It is also a correctness risk. A test that scans or flushes `vmss:*` keys
can delete the dev tenant's real cache entries, because the dev tenant
isn't registered in `vmss_test`. To avoid this, the prune tests
already had to switch to their own Redis database by hand.

## What Changes

- `conftest.py` points the whole test process at its own storage and cache
  before any `vmss_api` import, the same way it already pins
  `DB_NAME=vmss_test`:
  - `STORAGE_ROOT` is set to a per-session temporary directory, removed at
    the end of the session.
  - The cache Redis is set to a dedicated database index, 15, and that
    database is flushed at the start and end of the session.
- The prune tests' hand-built Redis database 15 client is replaced by the
  suite-wide setting.
- `docs/features/configuration.md` notes that tests never touch dev
  storage or the dev cache.

There is no product behaviour change. This affects test infrastructure
only, so the change carries no spec delta (`skip_specs`).

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
<!-- None: test infrastructure only. -->

## Impact

- **Code:** `conftest.py`, `tests/test_prune_non_default_tenants.py`, and
  any test that asserts on the literal default `./var/storage` path (to be
  checked during apply).
- **Local data:** none. Dev storage and Redis database 0 stop growing from
  test runs.
