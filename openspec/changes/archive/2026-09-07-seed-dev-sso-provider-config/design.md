## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `SsoProvider` (`sso/models.py`) is a tenant-scoped table, one row per
  tenant by app convention. `sso/service.py::save_provider_config(tenant_db,
  payload: SsoProviderConfigIn)` upserts it (encrypts the secret via
  `core/encryption.py`, computes a masked display value) with **no
  reachability validation at save time** — that only happens later, at
  actual login, via `oidc_client.fetch_discovery_document`.
- `fetch_discovery_document` enforces `https://`-only and rejects any URL
  resolving to a private/loopback/link-local/reserved address
  (`UnsafeDiscoveryUrlError`) — deliberate SSRF hardening
  (`security-architecture.md`). This cannot be relaxed for dev convenience
  without weakening a real security control.
- `scripts/seed_dev_data.py` already follows an idempotent, direct-call
  pattern: it resolves or creates the tenant, then calls service-layer
  functions (`seed_default_roles(tenant_db)`) inside `tenant_session_scope`,
  safe to re-run.
- `core/config.py` declares every `SSO_*` setting as `Field(default=None,
  alias="SSO_...")` on the `pydantic-settings` `Settings` class
  (`database-architecture.md` §8's "never read `os.environ` directly"
  rule).

## Goals / Non-Goals

**Goals:**
- Let a developer who has real OIDC test-app credentials (from any provider
  reachable over the public internet) get a working `SsoProvider` row seeded
  automatically, by setting environment variables once.
- Never break an existing dev workflow that doesn't set these variables —
  the new step must be a no-op by default.
- Keep the client secret handled exactly the way `PUT /auth/sso/config`
  already handles it (encrypted at rest, never logged) — no parallel,
  less-careful path for "the seeded one."

**Non-Goals:**
- Making a placeholder/fake discovery URL work — impossible without
  weakening the SSRF check, which is out of scope entirely.
- Standing up a local IdP container (Dex/Keycloak) — the user explicitly
  chose the lighter option over this.
- Touching `scripts/provision_tenant.py` — real customer tenant
  provisioning must never pick up dev/test IdP credentials from `.env`.

## Decisions

- **Reuse `save_provider_config` from the seed script rather than
  constructing an `SsoProvider` row by hand.** This guarantees the seeded
  row gets the identical encryption/masking treatment a real admin action
  would produce — no second, ad hoc code path for turning a plaintext
  secret into a stored row. *Alternative considered*: direct ORM insert
  with `encryption.encrypt()` called inline in the seed script. Rejected —
  duplicates logic that already exists and risks drifting from it (e.g. if
  masking logic changes later, the seed script would need a second, easy-
  to-forget update).
- **Gate the step on all three required settings being present, not a
  single boolean flag.** A `SSO_DEV_SEED_ENABLED=true` flag with the other
  three still unset would need its own error handling for "flag on but no
  credentials" — checking presence of the actual credentials directly is
  simpler and self-documenting: if you haven't filled in real values, the
  step silently does nothing, exactly the same outcome as not touching
  `.env` at all.
- **Display name defaults rather than being required.** `SSO_DEV_SEED_DISPLAY_NAME`
  defaults to `"Dev SSO Provider"` since it carries no security or
  correctness weight (it's cosmetic — shown in `GET /auth/sso/config` and
  the web config screen) — no reason to force a developer to set a fourth
  variable just to seed successfully.
- **Idempotent upsert, matching the existing role-reseed pattern.**
  Re-running `seed_dev_data.py` after changing the three env vars (e.g.
  rotating a test app's secret) updates the existing row via
  `save_provider_config`'s existing `get_any()`-then-update branch, rather
  than erroring on "already exists" or leaving a stale row — consistent
  with this script's existing "safe to re-run, always re-syncs" philosophy
  for roles/migrations.
- **New settings follow the exact `Field(default=None, alias="SSO_...")`
  pattern already used for `sso_encryption_key` etc.**, so
  `pydantic-settings` validation, `.env.example` conventions, and the "never
  read `os.environ` directly" rule all apply uniformly — no bespoke parsing.

## Risks / Trade-offs

- [A developer sets the three variables but points `discovery_url` at a
  non-`https://` or private-resolving address, expecting seeding to "just
  work"] → The seed step still succeeds (no reachability check at save
  time, per `save_provider_config`'s existing behavior) but `start_login`
  will still 409/fail at actual login time with the SSRF error — mitigated
  by the new docs section explaining this constraint explicitly *before* a
  developer tries to configure anything, not after they hit a second
  confusing error.
- [A developer's real test-IdP client secret ends up committed to a local
  `.env` and accidentally pushed] → Same risk every other `.env` secret
  already carries in this repo (`git-workflow.md` §5/§6 already governs
  this: `.env` is excluded from broad `git add`, `.env.example` gets a
  placeholder instead) — no new mitigation needed beyond what's already in
  place, but the new doc section explicitly calls out "these are real
  credentials, treat them like the other `SSO_*` secrets."
- [Re-seeding silently overwrites a row a developer configured by hand via
  `PUT /auth/sso/config`, if they happen to also have the three env vars set]
  → Documented as expected upsert behavior (same "re-running re-syncs"
  philosophy as roles), not a bug — a developer who wants to manage the
  config purely through the API should simply not set the three env vars.

## Migration Plan

Purely additive: new optional settings default to `None` (feature is a
no-op until configured), new seed step only runs when fully configured,
`.env.example` gains new documented-but-blank entries, docs gain a new
section. No rollback beyond reverting the diff — no schema, data, or API
contract changes are involved.
