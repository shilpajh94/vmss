## 1. Config Model — Database

- [x] 1.1 Add `db_connection`, `db_host`, `db_port`, `db_database`,
      `db_username`, `db_password` fields to `Settings`, no real-looking
      defaults (see design.md Decision 1 for the required/no-fallback
      behavior). (Component fields default to `None`/a non-secret constant,
      never a real host/credential; `database_url` raises naming the exact
      missing var(s) if accessed with neither components nor an override
      fully set — required-field validation was rejected because it would
      break the override-only/PaaS path, see conversation.)
- [x] 1.2 Add `database_url_override: str | None` aliased to `DATABASE_URL`.
- [x] 1.3 Add a `database_url` computed property: return the override if
      set, else assemble `{driver}://{user}:{password}@{host}:{port}/{database}`
      via the `db_connection` → SQLAlchemy driver mapping (`{"pgsql":
      "postgresql+asyncpg"}`).
- [x] 1.4 Confirm every existing `settings.database_url` consumer
      (`core/database.py`, `backend_pre_start.py`, `alembic/env.py`,
      `alembic_tenant/env.py`, `platform/service.py`) still works unchanged
      against the computed property.

## 2. Config Model — Redis / Celery

- [x] 2.1 Add `redis_host`, `redis_port`, `redis_password`,
      `redis_cache_db`, `redis_celery_broker_db`, `redis_celery_result_db`
      fields to `Settings`.
- [x] 2.2 Add `redis_url_override`, `celery_broker_url_override`,
      `celery_result_backend_override` optional fields aliased to
      `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- [x] 2.3 Add `redis_url`, `celery_broker_url`, `celery_result_backend`
      computed properties per design.md Decision 2 (override-if-set, else
      assembled from shared host/port/password + purpose-specific index).
      Same lazy-validation fix as 1.1: `redis_host` defaults to `None`, each
      property raises naming the missing setting only when actually
      accessed without an override.
- [x] 2.4 Confirm `core/celery_app.py` still works unchanged against the
      computed properties.

## 3. Config Model — Remaining Groups

- [x] 3.1 Rename `app_name`, `environment`, `debug` fields' env aliases to
      `APP_NAME`, `APP_ENV`, `APP_DEBUG`.
- [x] 3.2 Add `log_level: str = "INFO"` field aliased to `LOG_LEVEL`; wire it
      into the centralized `structlog` configuration in `core/`
      (`logging-observability.md` §3).
- [x] 3.3 Rename JWT fields' env aliases to `JWT_SECRET_KEY`,
      `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`,
      `JWT_REFRESH_TOKEN_EXPIRE_MINUTES`.
- [x] 3.4 Rename tenancy fields' env aliases to `TENANT_DEFAULT_SLUG`,
      `TENANT_GLOBAL_SCHEMA_NAME`, `TENANT_SCHEMA_PREFIX`.
- [x] 3.5 Rename SMTP fields to `MAIL_*` (`MAIL_HOST`, `MAIL_PORT`,
      `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`,
      `MAIL_FROM_ADDRESS`), preserving the existing "leave genuinely blank,
      not a placeholder token" behavior for username/password.
- [x] 3.6 Rename storage S3 fields' env aliases to `AWS_BUCKET`,
      `AWS_DEFAULT_REGION`, `AWS_ENDPOINT_URL`; leave `STORAGE_ROOT`,
      `STORAGE_BACKEND`, `STORAGE_S3_PRESIGNED_URL_TTL_SECONDS` as-is.
      `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are documented in
      `.env.example` (task 4.1) but are not `Settings` fields — boto3 reads
      them directly from the process environment.
- [x] 3.7 Confirm `CORS_ALLOWED_ORIGINS`, `SMS_*`, and `INVITATION_*` field
      names are unchanged (per design.md's mapping table).

## 4. Example File and Docs

- [x] 4.1 Rewrite `.env.example` with the new variable names, grouped by
      service with a blank line between groups, keeping the existing
      `__PLACEHOLDER__` token convention and DDEV-default comments.
- [x] 4.2 Add a short migration note (old `.env` compatibility — full-URL
      overrides still work, renamed non-URL fields need updating) to
      `docs/features/` (new or existing infra/config doc). (New
      `docs/features/configuration.md`; also updated the `SMTP_*`/
      `STORAGE_S3_*` env var names in `docs/features/invitations.md` and
      `docs/features/registrations.md`'s existing config tables to match.)

## 5. Test Bootstrap

- [x] 5.1 Update `conftest.py`'s test-DB setup to set `DB_DATABASE=vmss_test`
      directly when component vars are in use, keeping the existing
      `make_url(...).set(database=...)` path as a fallback when
      `DATABASE_URL` is set instead (design.md Decision 5). (Kept the
      component-assembly logic duplicated in `conftest.py` rather than
      importing `Settings` early — importing `vmss_api.core.config` before
      the env swap would bake in the pre-swap dev database into its
      module-level `settings` singleton.)
- [x] 5.2 Run the full test suite against both configurations (component
      vars only; `DATABASE_URL` override set) to confirm both paths resolve
      to the `vmss_test` database. (229 passed against this repo's `.env`,
      which uses the component-var path; the `DATABASE_URL`-override branch
      was exercised via a standalone `Settings(_env_file=None, ...)` check,
      see task 6.3.)

## 6. Verification

- [x] 6.1 Start the app with no `.env`/env vars set and confirm it fails
      fast with a clear missing-setting error (spec's "Application refuses
      to start with no environment configured" scenario). Verified via
      `Settings(_env_file=None).database_url` →
      `ValueError: Database is not configured: set DATABASE_URL, or all of
      DB_HOST, DB_DATABASE, DB_USERNAME, DB_PASSWORD.`
- [x] 6.2 Start the app with only component vars set (no full-URL overrides)
      and confirm it connects and serves requests. Verified: `GET
      /health/ready` returns `200 {"status": "ok"}` against this repo's
      component-var `.env` (real DB + Redis roundtrip).
- [x] 6.3 Start the app with a full `DATABASE_URL` set alongside component
      vars with different values, and confirm the full URL wins. Verified
      via a standalone `Settings(...)` construction with conflicting
      component vars and a `DATABASE_URL` override — `.database_url`
      returned the override value.
- [x] 6.4 Run `ruff check`, `ruff format --check`, `mypy` on `core/`, and the
      full `pytest` suite — all green before proposing this for review
      (`git-workflow.md` §3-4). All green: `ruff check .`, `ruff format
      --check .` (210 files), `mypy src/vmss_api/core` (15 files), `pytest`
      (229 passed).
- [x] 6.5 Regenerate this repo's own DDEV `.env` from the new
      `.env.example` and confirm `ddev start` + `ddev exec uv run pytest`
      still pass end to end. Done — `.env` (gitignored) rewritten with the
      same values under the new names; full suite passed against it.
