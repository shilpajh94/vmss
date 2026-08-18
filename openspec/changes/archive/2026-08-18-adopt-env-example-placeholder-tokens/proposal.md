## Why

`.env.example` currently ships real, ready-to-use values for every setting
(`DATABASE_URL=postgresql+asyncpg://db:db@db:5432/db`,
`JWT_SECRET_KEY=change-me-in-env`, etc.). The user wants the convention other
frameworks use (e.g. Symfony recipe blocks: `OAUTH_PRIVATE_KEY=__OAUTH_PRIVATE_KEY__`)
instead: every value in `.env.example` becomes an explicit `__VARNAME__`
placeholder token, making it visually unmistakable that a value must be
deliberately filled in — including infra defaults that happen to already be
correct for local DDEV — rather than silently inherited from the template.

## What Changes

- Rewrite every `KEY=value` line in `.env.example` to `KEY=__KEY__` (the
  double-underscore token matching the variable's own name), covering all 21
  settings currently in the file — not just secrets.
- Preserve every existing explanatory comment (DDEV service-topology notes,
  the JWT-secret-generation snippet, the SMS/schema/invitation notes) and add
  one to any setting that doesn't already have one, so the placeholder alone
  doesn't leave a developer guessing what value actually belongs there.
- **BREAKING (developer-workflow only, not runtime)**: `.env.example` no
  longer works "as-is" after a plain `cp .env.example .env` —
  `README.md`'s quick-start (`cp .env.example .env # then set a real
  JWT_SECRET_KEY`) currently implies only the JWT secret needs a real value;
  every placeholder now needs one. Update that README step accordingly.
- No change to the local, gitignored `.env` file itself — it already holds
  real values (fixed during the `pre-commit-quality-audit` change) and stays
  untouched; only the tracked template changes.
- No change to `core/config.py` or any runtime code — `.env.example` is never
  loaded by the application (`pydantic-settings`' `env_file=".env"` only), so
  this is a template/documentation-only change with zero effect on the
  running app.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this only changes a non-runtime template file and its accompanying
documentation. No API, schema, or application behavior changes. This change
sets `skip_specs: true` in `.openspec.yaml` accordingly.

## Impact

- **Affected files**: `.env.example` (all 21 settings rewritten to
  placeholder tokens), `README.md` (the quick-start `.env` step's wording).
- **No dependency, schema, or code changes.**
- **Developer-workflow trade-off** (see design.md): onboarding via
  `cp .env.example .env` no longer "just works" for DDEV-fixed values
  (`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`,
  `CELERY_RESULT_BACKEND`) — a developer must now look up and paste in the
  same value that used to be there by default. This is the explicit,
  deliberate choice made for this change (uniform placeholder convention
  over turnkey defaults), not an oversight.
