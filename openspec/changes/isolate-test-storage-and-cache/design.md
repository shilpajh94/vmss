## Context

`conftest.py` sets `os.environ["DB_NAME"] = "vmss_test"` before importing
`vmss_api`, because the engine is built at import time. Storage and Redis
are resolved the same way:
- `settings.storage_root` defaults to `./var/storage`, which is the dev
  folder inside the container.
- The cache Redis client (`core/redis.py::redis_client`) is built at import
  time from `settings.redis_url`.

The local `.env` sets a full `REDIS_URL`, and `_redis_url()` returns that
override verbatim. So a `REDIS_CACHE_DB` index alone would be ignored.

## Goals / Non-Goals

**Goals:** a test run never writes to dev storage or the dev cache
database, and the setup is in one place.

**Non-Goals:** changing the Celery broker and result databases (tests run
tasks eagerly or monkeypatch them; check this during apply), or moving
tests off the shared DDEV Redis server.

## Decisions

### 1. Set the environment before import, in `conftest.py`
At the top of `conftest.py`, next to `DB_NAME`:
- `STORAGE_ROOT`: a `tempfile.mkdtemp(prefix="vmss-test-storage-")`,
  removed by a session finaliser.
- Redis: process environment variables take precedence over `.env` in
  pydantic-settings. So conftest sets `REDIS_URL` to the test database,
  built from `REDIS_URL` if it is already in the environment, otherwise
  from `REDIS_HOST`/`REDIS_PORT` or the `.env` value, with the database
  path segment replaced by `/15`.

To avoid parsing `.env` by hand, the implementation can set
`REDIS_CACHE_DB=15` and set `REDIS_URL` to an empty string, so the
override is falsy and the host-based URL is used. This only works if the
`.env` defines `REDIS_HOST`; it does today. Pick whichever works, and
verify by printing `settings.redis_url` inside a test.

### 2. Flush the test database, never database 0
A session-scoped autouse fixture runs `FLUSHDB` against the database-15
client at the start and end of the session. It asserts that the client's
database index is 15 before flushing.

### 3. Prune tests use the suite setting
The `redis` fixture in `tests/test_prune_non_default_tenants.py` uses
`get_redis()` once the suite-wide database is 15. Its own database-15
client is removed.

## Risks / Trade-offs

- [A test asserts on the literal `var/storage` path] → Search for
  `var/storage` and `storage_root` in tests during apply, and switch them
  to `settings.storage_root`.
- [Running two pytest processes at once still shares Redis database 15] →
  Already disallowed (see the project note on concurrent pytest). No change.
