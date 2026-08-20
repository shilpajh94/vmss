# Configuration (Environment Variables)

Every runtime setting is read from the environment via `pydantic-settings`
(`src/vmss_api/core/config.py::Settings`) — never hardcoded, never read from
`os.environ` directly outside that one module (`database-architecture.md`
§8). `.env.example` documents every variable the app reads; copy it to
`.env` and fill in real values before running the app.

## Naming convention

Variables are grouped by service with a `SCREAMING_SNAKE_CASE`, prefixed
name (`APP_*`, `DB_*`, `REDIS_*`, `JWT_*`, `MAIL_*`, `AWS_*`, `TENANT_*`,
`STORAGE_*`, `SMS_*`, `INVITATION_*`), matching the convention used across
the team's other projects.

## Database

The connection is built from component variables, not a single hardcoded
DSN:

| Variable | Default | Purpose |
|---|---|---|
| `DB_CONNECTION` | `pgsql` | Driver key — only `pgsql` is supported (this project is Postgres-only). |
| `DB_HOST` | none — required | Postgres host. |
| `DB_PORT` | `5432` | Postgres port. |
| `DB_DATABASE` | none — required | Database name. |
| `DB_USERNAME` | none — required | Database user. |
| `DB_PASSWORD` | none — required | Database password. |
| `DATABASE_URL` | unset | **Optional full-URL override.** If set, it is used as-is and the `DB_*` component variables above are ignored entirely. Set this on a platform that injects one connection string at deploy time (e.g. many PaaS providers); leave it unset everywhere else. |

If neither `DATABASE_URL` nor all of `DB_HOST`/`DB_DATABASE`/`DB_USERNAME`/
`DB_PASSWORD` are set, the app fails fast at startup with an error naming
exactly which setting is missing — it will never silently fall back to a
hardcoded connection target.

## Redis / Celery

One Redis instance, one logical database index per purpose:

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_HOST` | none — required (unless every `*_URL` override below is set) | Shared Redis host. |
| `REDIS_PORT` | `6379` | Shared Redis port. |
| `REDIS_PASSWORD` | unset | Only needed if Redis requires auth. |
| `REDIS_CACHE_DB` | `0` | Logical DB index for app caching. |
| `REDIS_CELERY_BROKER_DB` | `1` | Logical DB index for the Celery broker. |
| `REDIS_CELERY_RESULT_DB` | `2` | Logical DB index for the Celery result backend. |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | unset | **Optional full-URL overrides**, one per purpose. Each wins outright for that one purpose if set, independent of the others — e.g. you can point just the broker at a different Redis instance. |

## Other groups

See `.env.example` for the full, current list (it is kept in sync with
`Settings` — a setting with no entry there is a defect). Notable groups:
`APP_*` (name/environment/debug), `LOG_LEVEL`, `JWT_*` (auth token config),
`CORS_ALLOWED_ORIGINS`, `TENANT_*` (schema-per-tenant config,
`database-architecture.md` §2), `STORAGE_*`/`AWS_*` (file storage,
`docs/features/registrations.md`), `MAIL_*` (SMTP, `docs/features/invitations.md`),
`SMS_*`, `INVITATION_*`.

`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are **not** read by `Settings` —
boto3's default credential provider chain reads them directly from the
process environment when `STORAGE_BACKEND=s3`. They're documented in
`.env.example` for discoverability even though `core/config.py` never
touches them.

## Migrating an existing `.env`

This project used to declare `DATABASE_URL`/`REDIS_URL`/`CELERY_BROKER_URL`/
`CELERY_RESULT_BACKEND` as single DSN strings and left every other setting
unprefixed (`ENVIRONMENT`, `DEBUG`, `SMTP_*`, `DEFAULT_TENANT_SLUG`,
`GLOBAL_SCHEMA_NAME`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REFRESH_TOKEN_EXPIRE_MINUTES`, `STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`,
`STORAGE_S3_ENDPOINT_URL`). An existing `.env` from before this change needs
updating:

- Any `DATABASE_URL=...`/`REDIS_URL=...`/`CELERY_BROKER_URL=...`/
  `CELERY_RESULT_BACKEND=...` line **keeps working unchanged** — those are
  still read, now as explicit overrides that take precedence over the new
  component variables.
- Every other renamed variable (see the tables above and `.env.example`)
  needs its `.env` line updated to the new name, or the setting silently
  reverts to its default instead of erroring — regenerating `.env` from the
  current `.env.example` is the simplest way to pick up every rename at
  once.
- No database schema or data changes with this — this is process
  configuration only.
