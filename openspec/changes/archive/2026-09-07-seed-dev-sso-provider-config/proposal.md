## Why

Staff SSO login was manually tested (per `verify-invitation-rollout-regression`'s
checklist) and hit `{"success":false,"message":"SSO is not configured for this
tenant","errors":null}` (HTTP 409). Investigation confirmed this is **not a
code defect** — `start_login` correctly raises `SsoNotConfiguredError` when no
enabled `SsoProvider` row exists for the tenant's schema, exactly as
`sso/tests.py::test_login_initiate_without_configured_provider_returns_409`
already asserts. The real gap: neither `scripts/seed_dev_data.py` nor
`scripts/provision_tenant.py` ever creates an `SsoProvider` row, so every
freshly seeded dev tenant hits this by construction — there was nothing wrong
to click through.

A fully "just works" seeded default isn't achievable here: `fetch_discovery_document`
deliberately rejects any `discovery_url` resolving to a private/loopback/
reserved address (SSRF hardening — `security-architecture.md`'s posture, not
something to weaken for convenience), no local IdP container exists in the dev
stack, and a client secret is real credential material a seed script cannot
conjure. So this change is scoped to the achievable, low-risk fix: let a
developer who already has (or quickly creates) a real test OIDC app plug its
credentials into `.env` once, and have seeding pick them up automatically from
then on — plus a runbook explaining the SSRF constraint so nobody re-discovers
this 409 by surprise.

## What Changes

- `scripts/seed_dev_data.py` gains an **optional, opt-in** step: if three new
  settings (`SSO_DEV_SEED_DISCOVERY_URL`, `SSO_DEV_SEED_CLIENT_ID`,
  `SSO_DEV_SEED_CLIENT_SECRET`) are all present, it upserts an enabled
  `SsoProvider` row for the seeded tenant via the existing
  `sso/service.py::save_provider_config` (the same function `PUT
  /auth/sso/config` uses), idempotently — safe to re-run, consistent with
  this script's existing "always re-sync" pattern for roles/migrations. If any
  of the three are unset, seeding **silently skips this step** and behaves
  exactly as it does today — no seed run that previously worked starts failing
  because SSO isn't configured.
- A fourth optional setting, `SSO_DEV_SEED_DISPLAY_NAME` (default `"Dev SSO
  Provider"`), sets the seeded row's display name.
- `scripts/provision_tenant.py` is **explicitly not touched** — it is the same
  code path real-customer tenant provisioning uses
  (`POST /api/v1/platform/tenants`), and auto-attaching dev/test IdP
  credentials there would leak dev configuration into production tenant
  provisioning.
- `.env.example` documents the four new optional settings alongside the
  existing `SSO_*` block, each with a placeholder value and a one-line note
  that they're dev-seeding-only and require a real, publicly-reachable OIDC
  discovery endpoint.
- A new "Local Development Setup" section in `docs/features/sso_authentication.md`
  explains: why a placeholder/local discovery URL will not work (the SSRF
  check), how to obtain a free test OIDC app from a real provider (e.g. Auth0,
  Okta, Azure AD, Google) quickly, and how to set the four settings so
  `scripts/seed_dev_data.py` provisions the row automatically — with the
  existing manual `PUT /auth/sso/config` path documented as the fallback for
  anyone who'd rather configure it after the fact instead of via `.env`.
- No API contract, schema, or runtime behavior changes — `start_login`'s
  `SsoNotConfiguredError`/409 behavior is correct today and stays exactly as
  is; this only makes it easier to get past it in a dev environment when
  desired.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this is a dev-tooling and documentation change to `scripts/` and
`docs/`; no product-facing requirement of the `sso` capability changes.
`skip_specs: true` is set in this change's `.openspec.yaml`, consistent with
`project-rules.md`'s guidance that specs describe behavior and this change
introduces none.)

## Impact

- **Code**: `scripts/seed_dev_data.py` (new optional step), `src/vmss_api/core/config.py`
  (four new optional `Field(default=None, ...)` settings, following the
  existing `sso_*` pattern).
- **Config**: `.env.example` gains four new documented, blank-by-default
  entries.
- **Docs**: `docs/features/sso_authentication.md` gains a "Local Development
  Setup" section.
- **Not touched**: `scripts/provision_tenant.py`, any API endpoint, any
  existing `SsoProvider`/`SsoRoleMapping` model or migration, the SSRF
  reachability check itself.
- **No breaking change, no migration, no new dependency.**
