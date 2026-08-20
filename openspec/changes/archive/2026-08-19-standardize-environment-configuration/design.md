## Context

`src/vmss_api/core/config.py::Settings` is a single `pydantic-settings`
`BaseSettings` class read via the `settings` singleton everywhere
(`database-architecture.md` §8). Today it declares `database_url`,
`redis_url`, `celery_broker_url`, and `celery_result_backend` as plain `str`
fields whose defaults are complete, real, DDEV-matching DSNs. `.env.example`
mirrors that shape (one `DATABASE_URL=__PLACEHOLDER__` line per service,
comment above stating the DDEV-correct literal to paste in — established by
`openspec/changes/archive/2026-08-18-adopt-env-example-placeholder-tokens/`).
There is no CI/deploy pipeline file in this repo (deployment is DDEV-only
today per `git status`'s absence of `docker-compose*.yml`/`.github/workflows`)
and `project-rules.md` explicitly flags the eventual deployment target as
undecided. `conftest.py` currently gets the test DB by parsing
`DATABASE_URL` with `sqlalchemy.engine.make_url(...).set(database="vmss_test")`
and re-injecting the rebuilt string into `os.environ` before `vmss_api` is
imported (needed because `core/database.py` builds its engine at import
time).

See `proposal.md` - Why for the deployment-pipeline motivation, and
`specs/environment-configuration/spec.md` for the behavior this design
implements.

## Goals / Non-Goals

**Goals:**
- Remove every real-looking hardcoded connection default from `config.py`.
- Give every service group (DB, Redis/Celery, JWT, mail, SMS, storage, CORS,
  tenancy, invitations, logging) a consistent `SCREAMING_SNAKE_CASE`,
  service-prefixed variable naming scheme, matching the convention already
  used on the team's other (Laravel) projects.
- Support both a component-var input (`DB_HOST`, `DB_PORT`, ...) and a
  full-URL override (`DATABASE_URL`), so the app works unmodified on a local
  DDEV setup, a docker-compose stack, and a PaaS that injects one connection
  string, without a code branch per target.
- Keep the existing `__PLACEHOLDER__` token convention in `.env.example`
  (established convention, not up for revisiting here).

**Non-Goals:**
- Choosing a deployment target — still open per `project-rules.md`.
- Adding a CI pipeline file — none exists in-repo today; out of scope.
- Porting Laravel-specific concepts that don't map to this stack: sessions
  (`SESSION_*`), a queue *connection* setting (`QUEUE_CONNECTION`) — Celery's
  broker/backend already covers this — `BROADCAST_CONNECTION`, `CACHE_STORE`/
  `MEMCACHED_*` (Redis is the only cache backend here), `VITE_*` (no
  frontend build in this repo), and `BCRYPT_ROUNDS` (this project uses
  Argon2 per `security-architecture.md` §1, not bcrypt).
- Changing what `alembic/env.py`, `alembic_tenant/env.py`, or any other
  consumer of `settings.database_url` does — they keep reading that same
  attribute name unchanged; only how it's produced changes.

## Decisions

### 1. Component fields + computed property, not two parallel settings systems
`Settings` gains explicit fields for every component (`db_connection`,
`db_host`, `db_port`, `db_database`, `db_username`, `db_password`) and a
`@computed_field`/`@property` named `database_url` that:
1. Returns `os.environ["DATABASE_URL"]`-sourced value as-is if that variable
   is present and non-empty (checked via a dedicated optional field,
   `database_url_override: str | None = Field(default=None, alias="DATABASE_URL")`,
   so pydantic-settings — not a raw `os.environ` read — remains the single
   config entry point per `database-architecture.md` §8).
2. Otherwise assembles `{driver}://{user}:{password}@{host}:{port}/{database}`,
   where `driver` is resolved from `db_connection` through a small fixed
   mapping (`{"pgsql": "postgresql+asyncpg"}` today — this project is
   Postgres-only per `project-rules.md`; the mapping exists so `DB_CONNECTION`
   reads the same as the Laravel convention it mirrors, not to imply
   multi-database-engine support that doesn't exist).

Every existing consumer (`core/database.py`, `backend_pre_start.py`,
`alembic/env.py`, `alembic_tenant/env.py`, `platform/service.py`) keeps
calling `settings.database_url` unchanged — it's still a `str` from the
caller's point of view, just computed instead of stored. This is why the
proposal marks the field *rename* as breaking (env var names change) but
keeps `alembic`/`database.py` off the affected-files list — they're
insulated by the property.

**Alternative considered**: a `db_url_from_parts()` helper function called
explicitly at each consumption site instead of a computed property on
`Settings`. Rejected — it would require touching every consumer
(`database.py`, both `alembic/env.py` files, `platform/service.py`,
`backend_pre_start.py`) instead of none of them, for no behavioral benefit.

### 2. Redis/Celery: shared host/port, per-purpose logical DB index
Redis is used for three distinct purposes on one DDEV Redis instance
(cache DB 0, Celery broker DB 1, Celery result backend DB 2). Rather than
three independent `REDIS_HOST`/`REDIS_PORT` pairs (unnecessary duplication —
DDEV's `ddev-redis` add-on is one instance), the design uses one shared
`redis_host`/`redis_port`/`redis_password` plus three index fields:
`redis_cache_db` (default `0`), `redis_celery_broker_db` (default `1`),
`redis_celery_result_db` (default `2`). Three computed properties
(`redis_url`, `celery_broker_url`, `celery_result_backend`) assemble
`redis://[:password@]{host}:{port}/{index}` each, with the same
full-URL-override pattern as `database_url` (`REDIS_URL`,
`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` env vars, if set, win outright
for that one purpose — a deployment can override just the broker URL without
having to also override the cache URL).

**Alternative considered**: only a shared `REDIS_URL` with Celery deriving
its own DSNs by swapping the path segment. Rejected — it reintroduces the
same "string surgery on a DSN" pattern this change removes from the DB case,
and doesn't allow a deployment to point the broker at a different Redis
instance than the cache without also changing the cache's host.

### 3. Full-URL overrides are read as their own optional fields, not `os.environ`
`database-architecture.md` §8 mandates all config go through `settings`, not
raw `os.environ` reads. The override fields (`database_url_override`,
`redis_url_override`, `celery_broker_url_override`,
`celery_result_backend_override`) are ordinary optional `Settings` fields
with an explicit alias to the un-prefixed env var name (`DATABASE_URL`,
`REDIS_URL`, ...), keeping every value's origin inside the one
`pydantic-settings` model instead of a side-channel `os.environ.get(...)` in
`config.py`'s module body.

### 4. Naming convention: adopt the prefix grouping, not every Laravel field
Mapping table (env var → `Settings` field; unlisted current fields are
renamed 1:1 to their `SCREAMING_SNAKE_CASE` form with no shape change):

| Group | Env var(s) | Notes |
|---|---|---|
| App | `APP_NAME`, `APP_ENV`, `APP_DEBUG` | `environment`→`APP_ENV`, `debug`→`APP_DEBUG`, matching Laravel's `APP_*` prefix |
| Logging | `LOG_LEVEL` | New field; default `INFO` per `logging-observability.md` §3 |
| Database | `DB_CONNECTION`, `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`, optional `DATABASE_URL` | Decision 1 |
| Cache/Queue | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_CACHE_DB`, `REDIS_CELERY_BROKER_DB`, `REDIS_CELERY_RESULT_DB`, optional `REDIS_URL`/`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` | Decision 2 |
| Auth | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_MINUTES` | Grouped under a `JWT_` prefix (was unprefixed) for the same scan-by-service-name reason as the rest |
| CORS | `CORS_ALLOWED_ORIGINS` | Unchanged |
| Tenancy | `TENANT_DEFAULT_SLUG`, `TENANT_GLOBAL_SCHEMA_NAME`, `TENANT_SCHEMA_PREFIX` | Grouped under `TENANT_` (was `DEFAULT_TENANT_SLUG`, `GLOBAL_SCHEMA_NAME`, unprefixed) |
| Storage | `STORAGE_ROOT`, `STORAGE_BACKEND`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_BUCKET`, `AWS_ENDPOINT_URL`, `STORAGE_S3_PRESIGNED_URL_TTL_SECONDS` | Adopts Laravel's `AWS_*` names for the S3 credential set specifically, since those are recognizable across the team's projects; non-credential storage knobs keep the `STORAGE_` prefix |
| Mail | `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`, `MAIL_FROM_ADDRESS` | Renamed from `SMTP_*` to `MAIL_*` per the reference convention; same "leave genuinely blank, not a placeholder token" handling for username/password carries over unchanged |
| SMS | `SMS_GATEWAY_BASE_URL`, `SMS_GATEWAY_API_KEY`, `SMS_FROM_NUMBER` | Unchanged |
| Invitations | `INVITATION_TOKEN_TTL_HOURS`, `INVITATION_MAX_UPLOAD_SIZE_BYTES`, `INVITATION_MAX_GROUP_VISITORS` | Unchanged |

Fields not carried over from the reference Laravel example (with why):
`APP_KEY`/`BCRYPT_ROUNDS` (Argon2, no framework-level app key concept here),
`APP_URL` (no server-rendered views generating absolute links), `APP_LOCALE`/
`APP_FALLBACK_LOCALE`/`APP_FAKER_LOCALE` (no i18n or factory-faker
requirement yet), `APP_MAINTENANCE_*`, `PHP_CLI_SERVER_WORKERS` (Uvicorn
worker count is a process-manager/deploy concern, not an app setting today),
`SESSION_*` (JWT is stateless — `security-architecture.md` §1),
`BROADCAST_CONNECTION`, `FILESYSTEM_DISK` (superseded by `STORAGE_BACKEND`,
already an explicit `Literal["local", "s3"]`), `QUEUE_CONNECTION` (Celery's
broker URL already says this), `CACHE_STORE`/`CACHE_PREFIX`/`MEMCACHED_HOST`
(Redis only), `REDIS_CLIENT` (driver is fixed — `redis`/`celery` Python
libs, not swappable), `VITE_APP_NAME` (no frontend build here).

### 5. `conftest.py` overrides `DB_DATABASE`, not `DATABASE_URL`
With component vars available, the test bootstrap sets
`os.environ["DB_DATABASE"] = "vmss_test"` (falling back to reading whatever
`DB_HOST`/`DB_PORT`/etc. are already set to, same as today) before importing
`vmss_api`, instead of round-tripping through `make_url(...).set(...)`. If
`DATABASE_URL` is set in the test environment instead (CI running against a
platform-provided single URL), the existing `make_url(...).set(database=...)`
string-surgery path is kept as a fallback specifically for that case — so
this is additive, not a removal of the current mechanism.

## Risks / Trade-offs

- **[Every deployed environment's `.env` goes stale the moment this merges]**
  → The proposal already marks this **BREAKING**; `docs/features/` gets a
  short migration note (old `.env` keeps working for any override var it
  already sets, e.g. an existing `DATABASE_URL=...` line still works via
  Decision 1's override path — only environments relying on the *renamed*
  non-URL fields, e.g. bare `ENVIRONMENT=`/`DEBUG=`/`SMTP_*`/`DEFAULT_TENANT_SLUG`
  without a corresponding full-URL override, need a same-day `.env` update).
- **[`DB_CONNECTION=pgsql` implies multi-driver support that doesn't exist]**
  → Documented in Decision 1 as a naming-convention concession, not a
  feature; the mapping table has exactly one entry and a config-time error
  (invalid value → the standard `pydantic` validation error at startup, per
  the spec's "startup fails naming the missing setting" requirement) is
  raised for anything else.
- **[Silent misconfiguration if both component vars and a full-URL override
  are set with different values]** → Not a bug: the full URL always wins,
  by design (Decision 1/2), and this is exactly the PaaS scenario the
  override exists for. `docs/features/` calls this precedence out explicitly
  so it isn't rediscovered by surprise during a deploy.

## Migration Plan

1. Land the `Settings` field changes, computed properties, and
   `.env.example` restructure in one commit (they're inseparable — a partial
   rename would desync the example file from the actual field names).
2. Update `conftest.py`'s test-DB bootstrap (Decision 5).
3. Regenerate local `.env` files (each developer, from the new
   `.env.example`) and the deploy environment's variables before the next
   deploy — call this out explicitly in the proposal's Impact section and in
   `docs/features/` (already done in `proposal.md`).
4. No data migration, no Alembic revision — this is process-environment
   configuration only, nothing persisted in the database changes shape.
5. **Rollback**: revert the commit; the previous `.env`/`.env.example` shape
   works again immediately since no schema or data changed.
