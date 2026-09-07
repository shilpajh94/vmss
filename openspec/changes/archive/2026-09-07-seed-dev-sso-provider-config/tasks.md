## 1. Settings

- [x] 1.1 Add four new optional settings to `core/config.py`, following the
      exact `Field(default=None, alias="SSO_...")` pattern already used for
      `sso_encryption_key`/`sso_redirect_uri`: `sso_dev_seed_discovery_url`
      (`SSO_DEV_SEED_DISCOVERY_URL`), `sso_dev_seed_client_id`
      (`SSO_DEV_SEED_CLIENT_ID`), `sso_dev_seed_client_secret`
      (`SSO_DEV_SEED_CLIENT_SECRET`), and `sso_dev_seed_display_name`
      (`SSO_DEV_SEED_DISPLAY_NAME`, default `"Dev SSO Provider"` — a plain
      string default, not `None`, since it's cosmetic-only).
- [x] 1.2 Add the four corresponding entries to `.env.example`, in the
      existing `SSO_*` block, each blank by default with a one-line comment
      noting they're dev-seeding-only, require a real publicly-reachable
      discovery URL, and should be treated as real credentials (same
      handling as the other `SSO_*` secrets per `git-workflow.md` §6).

## 2. Seed Script

- [x] 2.1 In `scripts/seed_dev_data.py`, after the existing role/admin-user
      seeding inside the tenant session scope, add a step that checks
      whether `settings.sso_dev_seed_discovery_url`,
      `settings.sso_dev_seed_client_id`, and
      `settings.sso_dev_seed_client_secret` are all set (non-`None`,
      non-empty). **Placed before the `already_indexed` early return so a
      re-run always re-syncs it, matching the role-catalog re-sync's
      placement.**
- [x] 2.2 When all three are set, call
      `sso_service.save_provider_config(tenant_db, SsoProviderConfigIn(...))`
      with `display_name=settings.sso_dev_seed_display_name`,
      `discovery_url`, `client_id`, `client_secret` from the settings above,
      and `is_enabled=True`. Print a one-line confirmation (e.g. `SSO
      provider configured for tenant '<slug>'`).
- [x] 2.3 When any of the three are unset, skip the step entirely with no
      output change from today's behavior (no partial/warning message
      needed — this is the expected default state for anyone not opting
      in).
- [x] 2.4 Confirm `scripts/provision_tenant.py` is left untouched. **Verified:
      `grep -i sso scripts/provision_tenant.py` returns no matches; file not
      edited.**

## 3. Documentation

- [x] 3.1 Add a "Local Development Setup" section to
      `docs/features/sso_authentication.md` explaining: why a placeholder
      or local/private `discovery_url` will not work (the SSRF check in
      `oidc_client.fetch_discovery_document`), a pointer to getting a free
      test OIDC app from a real provider (Auth0, Okta, Azure AD, or Google
      all offer free tiers suitable for this), and the four `SSO_DEV_SEED_*`
      settings that make `scripts/seed_dev_data.py` provision the row
      automatically once set.
- [x] 3.2 Document the manual fallback in the same section: calling `PUT
      /auth/sso/config` directly (existing endpoint, unchanged) for anyone
      who'd rather configure SSO after seeding instead of via `.env`.

## 4. Verification

- [x] 4.1 Run `scripts/seed_dev_data.py` locally with none of the four
      settings set — confirm it completes exactly as it does today (no new
      output, no error, no `SsoProvider` row created). **Verified: ran with
      `.env` unset for all four `SSO_DEV_SEED_*` vars — output identical to
      pre-change behavior, no SSO-related lines.**
- [x] 4.2 Set all three required settings to values for a real test OIDC
      app (or a syntactically valid placeholder if no real app is available
      in this session) and re-run the script — confirm an `SsoProvider` row
      is created/updated for the tenant, `is_enabled=True`, and that
      `ruff check`, `ruff format --check`, and `mypy` (scoped to `core` per
      `project-rules.md`) stay clean on the touched files. **No real test
      IdP was available this session; used syntactically valid placeholder
      values as the task explicitly allows. Verified via direct DB query:
      row created with `is_enabled=t`, correct `display_name`/`client_id`/
      `discovery_url`. `ruff check`, `ruff format --check`, and `mypy`
      (`core` + the seed script) all clean.**
- [x] 4.3 Re-run the script a second time with the same settings — confirm
      it updates the existing row rather than erroring or duplicating it
      (idempotency, matching the existing role-reseed pattern). **Verified:
      re-ran with rotated client_id/secret — row count stayed at 1, updated
      to the new client_id, no error. Test row deleted afterward to leave
      the local dev DB clean.**
