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

## `APP_DEBUG` is only ever honored in `local`/`testing`

`APP_DEBUG` alone does not control whether the running app exposes verbose,
framework-level error responses (a full stack trace instead of the standard
`{success, message, errors}` envelope on an unhandled exception). The app
computes an effective debug flag from both `APP_ENV` and `APP_DEBUG`
(`Settings.effective_debug`): debug behavior is only ever enabled when
`APP_ENV` is `local` or `testing`, regardless of what `APP_DEBUG` is set to.
Setting `APP_DEBUG=true` in `staging`/`production` has no effect — the app
still returns the standard error envelope on an unhandled exception, never a
raw traceback. This exists specifically so a deployment that forgets to set
`APP_DEBUG=false` doesn't expose internal details to callers
(`security-architecture.md` §4).

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

## Badge print flow

The reception badge-printing flow (`docs/features/checkin_badge.md`) is live
for a tenant only when its own `badgePrintFlowEnabled` toggle is on;
otherwise every `/checkin` endpoint returns `404`. The day-bound badge QR
token key is derived from `JWT_SECRET_KEY`. `BADGE_SCAN_RATE_LIMIT` (default
`30/minute`) limits the unauthenticated scan endpoints per IP.

## Provisioning the default tenant/branch

`TENANT_DEFAULT_SLUG` and `REGISTRATION_DEFAULT_BRANCH_CODE` back the
unauthenticated fallback several public endpoints use when a request carries
no tenant/device credential at all — the web portal's walk-in registration,
visit-info lookups, identity verification (OTP), and invitation tracking
(`docs/features/registrations.md`'s "Fallback when no `X-Device-Key` is sent
at all"). Setting these two variables in `.env` is not enough on its own:
the tenant named by `TENANT_DEFAULT_SLUG` and a branch with `code` equal to
`REGISTRATION_DEFAULT_BRANCH_CODE` must actually exist and be active in that
environment's database, or every one of those public endpoints rejects every
header-less request with a 401/404 server-misconfiguration response.

A new environment needs this as an explicit provisioning step, not something
discovered by a failing live request:

1. Provision a tenant whose slug matches `TENANT_DEFAULT_SLUG` (local dev:
   `scripts/seed_dev_data.py` does this against the values already in
   `.env`; any other environment provisions one the same way
   `platform/service.py::create_tenant` does, then sets `TENANT_DEFAULT_SLUG`
   to match its slug).
2. Within that tenant's schema, provision a branch whose `code` matches
   `REGISTRATION_DEFAULT_BRANCH_CODE` (default `MAIN`) and confirm it's
   active.
3. `GET /health/ready` verifies both of these resolve, in addition to
   Postgres/Redis connectivity — a deployment missing either reports
   unready (503) with a message naming which one, instead of reporting
   healthy until a real caller hits the walk-in/visit-info/OTP/tracking
   endpoints and gets rejected.

## Resetting and re-seeding dev data

To get a fully fresh local dev dataset spanning every feature (org
structure, visitor categories, invitations, OTP requests, a walk-in
registration) instead of only the minimal tenant/branch/admin
`seed_dev_data.py` provisions on its own, run these three scripts in
sequence:

```
ddev exec uv run python scripts/reset_dev_tenant_data.py --yes
ddev exec uv run python scripts/seed_dev_data.py
ddev exec uv run python scripts/seed_demo_workflow.py
```

`reset_dev_tenant_data.py` clears every row in the one tenant named by
`TENANT_DEFAULT_SLUG` (`TRUNCATE`, not a schema drop — its migration state
is untouched) plus that tenant's rows in the handful of global-schema
tables that reference it (`tenant_user_index`, `registration_device_keys`,
`platform_audit_events`). It never touches a second tenant's data, refuses
outright when `APP_ENV`/`settings.environment` is `production`, and without
`--yes` only prints what it *would* clear and exits — it performs no
partial or automatic action, since this is the one script in this
directory whose entire job is destructive. `seed_dev_data.py` then
re-provisions the tenant/branch/admin (idempotent either way), and
`seed_demo_workflow.py` (real HTTP, additive, safe to re-run) populates the
rest.

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
