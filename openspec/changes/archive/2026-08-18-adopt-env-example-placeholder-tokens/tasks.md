## 1. Rewrite `.env.example`

- [x] 1.1 Replace `APP_NAME`, `ENVIRONMENT`, `DEBUG` values with
      `__APP_NAME__`, `__ENVIRONMENT__`, `__DEBUG__`; add a one-line comment
      above each giving the DDEV-default value (`"VMSS API"`, `local`, `true`).
- [x] 1.2 Replace `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`,
      `CELERY_RESULT_BACKEND` values with their `__KEY__` placeholders,
      keeping/adding a comment stating the exact DDEV-default connection
      string for each.
- [x] 1.3 Replace `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
      `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_MINUTES` values
      with placeholders — keep the existing secret-generation comment on
      `JWT_SECRET_KEY`; add short comments for the other three stating their
      current defaults (`HS256`, `30`, `10080`).
- [x] 1.4 Replace `CORS_ALLOWED_ORIGINS`, `DEFAULT_TENANT_SLUG` values with
      placeholders, each with a comment giving the current default
      (`["http://localhost:3000"]`, `default`).
- [x] 1.5 Replace `GLOBAL_SCHEMA_NAME`, `TENANT_SCHEMA_PREFIX` values with
      placeholders — keep the existing `database-architecture.md §2` comment,
      extend it to state the literal defaults (`global`, `tenant_`).
- [x] 1.6 Replace `STORAGE_ROOT` value with its placeholder — keep the
      existing comment, extend it with the literal default (`./var/storage`).
- [x] 1.7 Replace `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_FROM_ADDRESS`
      values with placeholders (literal defaults `localhost`, `1025`,
      `false`, `no-reply@vmss.local` given in comments). `SMTP_USERNAME`/
      `SMTP_PASSWORD` deliberately did **not** get placeholder tokens — left
      genuinely blank with a comment explaining why (any non-empty value,
      including an un-filled-in placeholder, triggers aiosmtplib's
      AUTH-attempt bug fixed in `pre-commit-quality-audit`).
- [x] 1.8 `SMS_GATEWAY_BASE_URL`, `SMS_GATEWAY_API_KEY`, `SMS_FROM_NUMBER` —
      same treatment as `SMTP_USERNAME`/`SMTP_PASSWORD`: left genuinely blank
      (no placeholder token), with a comment cross-referencing the same
      "absent, not empty-string" reasoning.
- [x] 1.9 Replace `INVITATION_TOKEN_TTL_HOURS`, `INVITATION_MAX_UPLOAD_SIZE_BYTES`,
      `INVITATION_MAX_GROUP_VISITORS` values with placeholders — kept the
      existing "API-09-12" comment, added the literal defaults (`168`,
      `5242880`, `20`).

## 2. Update Onboarding Docs

- [x] 2.1 Rewrite `README.md`'s quick-start `.env` step (currently `cp
      .env.example .env    # then set a real JWT_SECRET_KEY`) to state that
      every placeholder now needs a real value, pointing at the per-line
      comments added in Task 1 as the source for the DDEV-fixed ones.

## 3. Verification

- [x] 3.1 Grep the codebase for any reference to `.env.example` outside
      `README.md`/`.gitignore`/`.aiignore`/`.dockerignore` (expected: none —
      confirm `core/config.py`'s `env_file` only ever points at `.env`) so
      this change is confirmed template-only with no runtime read path.
      **Confirmed: zero references in code/scripts/config; `env_file=".env"`
      only.**
- [x] 3.2 Run the full `ddev exec uv run pytest` suite — confirm all pass
      (expected: unaffected, since the app never reads `.env.example`).
      **189 passed, unaffected.**
- [x] 3.3 `ruff format --check .env.example` is not applicable (not a Python
      file) — instead, manually re-read the final `.env.example` top to
      bottom to confirm every one of the 21 settings follows the
      `KEY=__KEY__` pattern with no line missed. **Confirmed: 16 settings use
      `KEY=__KEY__`; the other 5 (`SMTP_USERNAME`, `SMTP_PASSWORD`,
      `SMS_GATEWAY_BASE_URL`, `SMS_GATEWAY_API_KEY`, `SMS_FROM_NUMBER`) are
      deliberately blank per Decision 4 — 16 + 5 = 21, all accounted for.**
