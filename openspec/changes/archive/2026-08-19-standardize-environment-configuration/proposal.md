## Why

The deployment pipeline is failing with database-related errors traced back to
`src/vmss_api/core/config.py::Settings.database_url`, which defaults to a
single real-looking DSN (`postgresql+asyncpg://db:db@db:5432/db`) instead of
being fully sourced from the environment. The same pattern exists for
`redis_url`, `celery_broker_url`, and `celery_result_backend`. Nothing in the
current `.env.example`/DDEV setup enforces that a hand-typed DSN string stays
in sync with the individual host/port/credential values it's assembled from
(`database-architecture.md` §8 already mandates settings-only config access;
this closes the gap in how the DB/Redis settings themselves are shaped), and
an undecided deployment target (`project-rules.md`) means the app cannot
assume it will always receive a single `DATABASE_URL` string the way DDEV's
local topology provides one today. Standardizing every setting group onto
explicit, component-based environment variables — the convention already used
on other projects the team maintains — removes the manual DSN-assembly step
that is the likely root cause of the pipeline's DB errors, and gives web/app
consumers a config surface that's consistent and auditable end to end.

## What Changes

- **BREAKING**: Replace `Settings.database_url` (a single hardcoded-default
  DSN string) with component fields — `db_connection`, `db_host`, `db_port`,
  `db_database`, `db_username`, `db_password` — and a computed
  `database_url` property that assembles the SQLAlchemy async DSN from those
  parts. If a `DATABASE_URL` environment variable is explicitly set (e.g. by
  a PaaS that injects one at deploy time), it is used as-is instead of the
  assembled value, so the app works unmodified on a platform that only
  provides a single connection string.
- **BREAKING**: Apply the same component-var + optional-full-URL-override
  pattern to Redis/Celery: `redis_host`, `redis_port`, `redis_password`, plus
  a per-purpose logical DB index (`redis_cache_db`, `redis_celery_broker_db`,
  `redis_celery_result_db`), with `REDIS_URL`/`CELERY_BROKER_URL`/
  `CELERY_RESULT_BACKEND` still honored as full-URL overrides if set.
- **BREAKING**: Rename remaining `Settings` fields to grouped,
  `SCREAMING_SNAKE_CASE`, service-prefixed environment variable names
  matching the team's established convention on other projects (`APP_NAME`,
  `APP_ENV`, `APP_DEBUG`, `LOG_LEVEL`, `JWT_*`, `MAIL_*` for SMTP, `SMS_*`,
  `AWS_*`/`STORAGE_*` for file storage, `CORS_*`, `TENANT_*`,
  `INVITATION_*`). Concepts from the reference Laravel `.env` that don't map
  to this stack (`SESSION_*`, `QUEUE_CONNECTION`, `BROADCAST_CONNECTION`,
  `CACHE_STORE`, `MEMCACHED_*`, `VITE_*`, `BCRYPT_ROUNDS`) are not adopted —
  see design.md for the full field-mapping table and rationale.
- Add a `log_level` setting (`LOG_LEVEL`, default `INFO`) read by the
  centralized `structlog` configuration in `core/`
  (`logging-observability.md` §3), replacing the implicit "whatever the
  library defaults to" behavior.
- Update `.env.example` to declare every new variable, grouped and commented
  the same way the reference file is (one blank-line-separated block per
  service), replacing the current single-DSN-per-service layout.
- Update `conftest.py`'s test-DB setup to override `DB_DATABASE` directly
  instead of parsing and rewriting a `DATABASE_URL` string.
- No change to `alembic/env.py`, `alembic_tenant/env.py`, or any other
  consumer of `settings.database_url` — they keep reading the same
  attribute name, which is now a computed property instead of a plain field.

## Capabilities

### New Capabilities
- `environment-configuration`: Defines how every runtime setting (database,
  cache/broker, auth, mail, SMS, storage, CORS, tenancy, logging) is sourced
  from environment variables — component-based per service with an optional
  full-URL override — with no hardcoded real-looking default for any
  connection string or credential.

### Modified Capabilities
- None. No existing spec file describes environment-variable shape; this is
  new spec-level ground, not a change to a previously specified behavior.

## Impact

- **Code**: `src/vmss_api/core/config.py` (field rename/restructure),
  `src/vmss_api/core/celery_app.py` (reads renamed Redis/Celery settings),
  `core/` logging setup (new `log_level` consumer), `conftest.py` (test-DB
  override mechanism).
- **Config**: `.env.example` fully restructured; every developer and
  deployment environment must regenerate its `.env` from the new template —
  the old single-line `DATABASE_URL=`/`REDIS_URL=` entries in an existing
  `.env` will no longer populate the renamed component fields unless that
  environment also sets the new `DB_*`/`REDIS_*` variables (or continues to
  set `DATABASE_URL`/`REDIS_URL` directly, which is still honored as an
  override).
- **Deployment**: this is the fix for the pipeline's DB-related failures —
  the deploy environment must be updated with the new `DB_*` variables (or a
  single `DATABASE_URL`) before the next deploy.
- **No API/HTTP contract change** — this is internal configuration plumbing
  only; no request/response shape, endpoint, or client-visible behavior is
  affected.
