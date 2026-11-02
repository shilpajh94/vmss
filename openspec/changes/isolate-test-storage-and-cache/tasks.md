## 1. Isolate Test Storage and Cache

- [x] 1.1 At the top of `conftest.py`, before any `vmss_api` import: set `STORAGE_ROOT` to a fresh temporary directory, and point the cache Redis at database 15 (an explicit `REDIS_URL`, or `REDIS_CACHE_DB=15` with an empty override; see design.md Decision 1). Remove the temporary directory at the end of the session.
- [x] 1.2 Add a session-scoped autouse fixture that checks the cache client is on database 15, then `FLUSHDB`s it at the start and end of the session
- [x] 1.3 *(Done differently, via audit-and-harden-api-and-web 2.1.)* Switch `tests/test_prune_non_default_tenants.py`'s `redis` fixture to `get_redis()` and drop its hand-built database-15 client. It now builds its client from `settings.redis_url`, which is database 15 for the whole suite, rather than calling `get_redis()`: the shared client's pooled connections can't cross the per-test event loops.
- [x] 1.4 Search the tests for literal `var/storage` or dev-path assumptions and fix any that break

## 2. Verify

- [x] 2.1 *(2026-10-21: dev `var/storage/vmss` had 876 entries before and after. Redis database 0 went from 122 to 102 `vmss:*` keys, which is TTL expiry; nothing new was written.)* Record the count of dev `var/storage/vmss/` entries and Redis database 0 `vmss:*` keys, run `pytest src/vmss_api/invitations tests/`, then check that both counts are unchanged
- [x] 2.2 Compare the suite's failure set against a run before the change, to confirm the change adds no new failures (see the project notes on pre-existing failures)
- [x] 2.3 Add a note in `docs/features/configuration.md` that tests use a temporary storage root and Redis database 15
