## 1. Dependencies & Configuration

- [x] 1.1 Move `httpx` from `[dependency-groups].dev` to `[project].dependencies`
      in `pyproject.toml`; add `cryptography` (PyJWT's RS256 backend + Fernet)
      to `[project].dependencies`; add `respx` to `[dependency-groups].dev`
      for mocking IdP HTTP calls in tests. Run `uv sync` and commit the
      updated `uv.lock`.
- [x] 1.2 Add new settings to `core/config.py`: `sso_encryption_key`
      (`SSO_ENCRYPTION_KEY`, no default — `core/encryption.py` must fail
      loudly at startup if unset, not silently no-op), `sso_frontend_callback_url`
      (`SSO_FRONTEND_CALLBACK_URL`), `sso_exchange_code_ttl_seconds` (default
      60). Add matching entries to `.env.example` using the repo's
      `__VAR__` placeholder convention for numeric defaults and a genuinely
      blank value for `SSO_ENCRYPTION_KEY`/`SSO_FRONTEND_CALLBACK_URL` (same
      "absent, not empty-string" posture as `MAIL_USERNAME`).
- [x] 1.3 Document, in a code comment on `sso_encryption_key`, how to
      generate a value (`python -c "from cryptography.fernet import Fernet;
      print(Fernet.generate_key().decode())"`) — a wrong-length key must
      fail fast and clearly, not produce a confusing runtime error deep in
      `core/encryption.py`.

## 2. Core: Secret Encryption

- [x] 2.1 Create `core/encryption.py` with `encrypt(plaintext: str) -> str`
      and `decrypt(ciphertext: str) -> str`, backed by
      `cryptography.fernet.Fernet(settings.sso_encryption_key)`.
- [x] 2.2 Add a `mask_secret(plaintext_tail_hint: str) -> str` helper (or
      store a small unencrypted `secret_last4` column — pick one and use it
      consistently) so `GET` on the SSO config can render `****1234` without
      ever decrypting the stored secret for display.
- [x] 2.3 Unit-style tests in `core/tests.py`: encrypt→decrypt round-trips;
      decrypting a tampered/corrupted ciphertext raises rather than
      returning garbage silently.

## 3. Data Model & Migration

- [x] 3.1 Add `SsoProvider` and `SsoRoleMapping` models to a new
      `src/vmss_api/sso/models.py` per `design.md`'s table shapes
      (`Base`, `TimestampMixin`, `UniqueConstraint` on
      `SsoRoleMapping.idp_group_claim_value` per tenant schema).
- [x] 3.2 Add `sso-config:manage` and `sso-config:view` to
      `auth/rbac_catalog.py::PERMISSION_CODES`, and grant both to the
      `admin` role's permission list.
- [x] 3.3 Author one new Alembic tenant revision under
      `alembic_tenant/versions/` creating `sso_providers` and
      `sso_role_mappings`. Matches the existing `op.create_table` precedent
      (e.g. `eb8de64c3468`) with no explicit `schema=` — the gotcha about
      `schema_translate_map` being ignored is specific to `op.add_column`/
      `op.drop_column` (confirmed against `39c3f5112585`), not
      `create_table`, which already resolves correctly through the
      connection-level translate map `alembic_tenant/env.py` sets up.
- [x] 3.4 Applied the new tenant migration and the updated permission
      catalog to the existing dev tenant schema (`ddev exec uv run alembic
      -c alembic_tenant.ini -x tenant_schema=tenant_default upgrade head`,
      then `ddev exec uv run python scripts/seed_dev_data.py` to re-sync the
      role catalog) — confirmed `sso-config:manage`/`sso-config:view` now
      show up under the `admin` role via a direct query.

## 4. OIDC Client

- [x] 4.1 Create `src/vmss_api/sso/oidc_client.py`: `fetch_discovery_document
      (discovery_url) -> DiscoveryDocument` (authorization_endpoint,
      token_endpoint, jwks_uri, issuer), `build_authorization_url(...)`,
      `exchange_code_for_tokens(...) -> dict` (POSTs to `token_endpoint`),
      `test_client_credentials(...)` for the connection-test check, and
      `verify_id_token(id_token, *, jwks_uri, issuer, audience, nonce)`
      using `jwt.PyJWKClient(jwks_uri)` + `jwt.decode(..., algorithms=
      ["RS256"], audience=..., issuer=...)`, additionally checking the
      token's `nonce` claim matches the expected value.
- [x] 4.2 Every outbound call opens a plain `httpx.AsyncClient()` internally.
      Deviation from the original plan for a manually injectable client:
      `respx` patches httpx's transport globally within its mocked context,
      so `sso/tests.py` intercepts these calls with `@respx.mock`/
      `respx.get(...)`/`respx.post(...)` without any constructor-injection
      scaffolding — simpler, and equally real-IdP-proof in CI.

## 5. Service Layer

- [x] 5.1 `src/vmss_api/sso/repository.py`: `SsoProviderRepository`,
      `SsoRoleMappingRepository` (both `TenantScopedRepository` subclasses).
- [x] 5.2 `src/vmss_api/sso/service.py::save_provider_config` /
      `get_provider_config` (masked) / `test_provider_config` (no
      persistence — fetch discovery doc, then attempt a client-credentials
      token request to validate `client_id`/`client_secret` without
      completing a real user flow).
- [x] 5.3 `service.py::create_role_mapping` / `list_role_mappings` /
      `delete_role_mapping`, validating the target role exists in this
      tenant (404 otherwise) before writing.
- [x] 5.4 `service.py::start_login(tenant_slug)`: resolve `Tenant` by slug
      (global schema, `TenantRepository`), resolve its enabled
      `SsoProvider` (404/409 if none), generate `state`+`nonce`, store a
      short-lived Redis record keyed by `state` alone (NOT tenant-prefixed —
      see design.md's amendment on why the state record can't be) ->
      `{tenant_id, nonce}` (TTL configurable, default 600s), return the
      built authorization URL.
- [x] 5.5 `service.py::handle_callback(code, state)`: look up and delete the
      Redis `state` record via `GETDEL` (atomic get-and-delete = single-use),
      4xx if missing/expired; resolve the tenant and its `SsoProvider` from
      the record (never from any other part of the callback request);
      exchange `code` for tokens via `oidc_client`; verify the ID token;
      call JIT provisioning (5.6); write the audit entries
      (`design.md`/spec's audited events); mint and return the exchange code.
- [x] 5.6 `service.py::_provision_or_resolve_user`: look up by email via
      `auth.repository.UserRepository`; if absent, call
      `auth.service.create_user` with a random unusable password (mirroring
      `sync_employee_directory`'s pattern) and the role resolved via
      `SsoRoleMappingRepository` against the token's `groups` claim,
      defaulting to the tenant's `host` role when no group matches or the
      claim is absent.
- [x] 5.7 `service.py::redeem_exchange_code(code)`: verify the signed
      exchange JWT (`type: "sso_exchange"`), atomically claim its `jti` in
      Redis via `SETNX` with the configured exchange-code TTL (fails closed
      on a race/replay), then issue the real token pair directly via
      `create_access_token`/`create_refresh_token` (no DB round-trip needed —
      every subsequent request re-validates the user anyway).
- [x] 5.8 Added `create_sso_exchange_token` to `core/security.py` alongside
      the existing `_create_token` family (short TTL, `jti` claim,
      `type: "sso_exchange"`), rather than building a second, parallel JWT
      helper inside `sso/`.

## 6. Router & Schemas

- [x] 6.1 `src/vmss_api/sso/schemas.py`: `SsoProviderConfigIn`,
      `SsoProviderConfigOut` (masked secret field), `SsoProviderTestRequest`/
      `Result`, `SsoRoleMappingIn`/`Out`, `SsoExchangeRequest`/`TokenResponse`
      (reuse `auth.schemas.TokenResponse` shape) — all `CamelModel` subclasses.
- [x] 6.2 `src/vmss_api/sso/router.py`:
      `GET/PUT /auth/sso/config` (`sso-config:manage`/`view`),
      `POST /auth/sso/config/test` (`sso-config:manage`),
      `GET/POST/DELETE /auth/sso/role-mappings` (`sso-config:manage`/`view`),
      `GET /auth/sso/{tenant_slug}/login` (public — redirect response),
      `GET /auth/sso/callback` (public — redirect response, no
      `response_model` since it 3xx-redirects rather than returning JSON),
      `POST /auth/sso/exchange` (public), `POST /auth/logout` (authenticated
      — writes the audit entry only, per `design.md`'s Non-Goals).
- [x] 6.3 Every JSON-returning route above declares `response_model=
      Envelope[<Schema>]` per `api-documentation.md` §1; registered
      `"sso"` in `main.py`'s `_TAGS_METADATA` with a description.
- [x] 6.4 Registered the router in `src/vmss_api/api.py`
      (`api_router.include_router(sso.router.router)`).

## 7. Auth Changes

- [x] 7.1 Tightened `POST /auth/login`'s `@limiter.limit(...)` in
      `auth/router.py` from `5/minute` to `3/minute`.
- [x] 7.2 Checked the existing rate-limit test
      (`auth/tests.py::test_login_rate_limit_trips`): it asserts "any 429
      across 10 requests" rather than hardcoding the old `5/minute` count,
      so it already passes unchanged against the new `3/minute` threshold —
      confirmed no test file anywhere hardcodes the numeric `5` for
      `POST /auth/login` specifically (`platform/tests.py`'s `range(6)` is
      the separate, unchanged superadmin-login limit). No test edit needed.
- [x] 7.3 Added `POST /auth/logout` per 6.2 — accepts the caller's bearer
      token (via `get_current_user`), writes an `AuditLog` entry
      (`action="logout"`), returns a bare success envelope.

## 8. Audit Logging

- [x] 8.1 Used `auth/audit.py::record_audit_log` as-is (it's already generic
      over `action`) rather than extending it — every mutating SSO
      call site passes one of `sso_login`, `sso_login_failed`,
      `sso_account_created`, `logout`, `sso_config_saved`,
      `sso_role_mapping_created`, `sso_role_mapping_deleted` and schedules
      it via `background_tasks.add_task(...)`, never inline. Also added
      `logger.warning(...)` lines (`sso_login_failed`,
      `sso_exchange_replay_rejected`) alongside the audit writes, matching
      `auth/service.py`'s login-failure logging convention
      (`logging-observability.md` §3's WARNING tier).
- [x] 8.2 Confirmed: `test_provider_config`'s failure messages are static,
      caller-safe strings (never interpolate the submitted secret);
      `put_config`'s audit `diff` only includes `displayName`/`isEnabled`,
      never `clientSecret`; no `logger.*` call anywhere in `sso/` passes the
      plaintext/encrypted secret or the raw ID token.

## 9. Tests (per `testing-standards.md` §2)

- [x] 9.1 Happy path for every new endpoint: save config → masked read;
      test-connection success; create/list/delete a role mapping; full
      login→callback→exchange flow against a `respx`-mocked IdP, asserting
      the returned token pair's claims.
- [x] 9.2 Permission-denied case: a caller without `sso-config:manage`
      hitting the config/role-mapping endpoints gets 403.
- [x] 9.3 Tenant-isolation case: tenant A's `SsoProvider` row is invisible
      to a session bound to tenant B's schema (`make_tenant_schema`/
      `open_tenant_session` fixtures, per `testing-standards.md` §2 and
      `auth/tests.py::test_tenant_schema_isolation`).
- [x] 9.4 Negative flow coverage per the new `sso-authentication` spec:
      unrecognized/replayed `state`; expired/tampered ID token
      (wrong-signature and expired-exp cases both covered — no separate
      wrong-audience case since the audience is always the tested tenant's
      own `client_id`, not client-controllable); reused exchange code;
      expired exchange code; login-initiate for a tenant with no enabled
      provider and for an unknown tenant slug.
- [x] 9.5 JIT-provisioning coverage: first-time login creates exactly one
      account with the mapped role; a second login by the same email
      resolves to the same account (no duplicate); an unmapped group
      defaults to `host`, never `admin`; a mapping can't target a
      nonexistent role.
- [x] 9.6 Confirmed `POST /auth/login` still authenticates a real
      password-holding user while a tenant has SSO enabled, and while no
      IdP route is mocked at all (proving login never calls out to the IdP)
      — the "no lockout" requirement.
- [x] 9.7 Added `SsoProviderFactory`/`SsoRoleMappingFactory` to
      `factories.py` and used them throughout `sso/tests.py`, not hand-built
      dicts (`testing-standards.md` §1). Found and fixed a real footgun
      along the way: `SsoRoleMappingFactory.build(role_id=...)` still lets
      polyfactory auto-generate and insert an unrelated nested `Role` via
      the `role` relationship, which then overwrites the explicit `role_id`
      on flush — fixed by passing `role=<the real Role object>` instead,
      matching how `conftest.py`'s `user` fixture already constructs
      `UserBranchRole` (relationship object, not raw FK id).
- [x] 9.8 `ddev exec uv run pytest` green — 345 passed (full suite, not
      just `sso/`), plus `ruff check`/`ruff format --check` clean on every
      file this change touched. Also discovered and worked around a
      genuine `jwt.PyJWKClient` testing gotcha (it fetches JWKS via
      `urllib.request`, not `httpx`, so `respx` can't intercept it — worked
      around with a `monkeypatch`-based stub, documented in `sso/tests.py`)
      and a genuine `BackgroundTasks`-during-exception gap in this app's
      exception-handling flow (documented in design.md and fixed in
      `sso/service.py`).

## 10. Documentation

- [x] 10.1 Added `docs/features/sso_authentication.md` (matches this repo's
      existing `docs/features/<feature>.md` naming, e.g. `identity_verification.md`):
      purpose, every endpoint, the login flow step-by-step, the
      role-assignment trust boundary, the Azure Entra ID groups-claim
      caveat, the new `.env` settings, and known limitations.
- [x] 10.2 Noted the `POST /auth/login` rate-limit change (5/minute →
      3/minute, and why) in both `docs/features/sso_authentication.md` and
      `docs/features/auth.md`'s endpoint table/"Not yet built" section
      (also updated there to remove "staff SSO login" from the not-built
      list and point at the new doc instead).

## 11. Manual End-to-End Verification (Microsoft Entra ID)

- [x] 11.0 Read-only sanity check (no client secret involved — discovery is
      a public, unauthenticated endpoint): confirmed
      `https://login.microsoftonline.com/192a4d7a-44fa-49f4-b052-b8e88940ae49/v2.0/.well-known/openid-configuration`
      resolves with `200` and returns a well-formed OIDC discovery document
      (`issuer`/`authorization_endpoint`/`token_endpoint`/`jwks_uri` all
      present) — the Directory (tenant) ID provided for this rollout is
      valid and reachable, and matches the shape
      `oidc_client.fetch_discovery_document` expects.
- [ ] 11.1 **Requires manual action outside this session** — an agentic CLI
      run has no browser and should not be the one typing a live client
      secret into a command it executes. In a local/dev `.env` only (never
      committed), set the Entra ID app registration's client ID and client
      secret already provisioned for this rollout (`0786c0f1-e333-4206-bba9-9f61eddcb66f` /
      the secret value shared out-of-band), the discovery URL from 11.0,
      and `SSO_ENCRYPTION_KEY`/`SSO_REDIRECT_URI`/`SSO_FRONTEND_CALLBACK_URL`.
- [ ] 11.2 Through the admin settings endpoint (`PUT /auth/sso/config`),
      save that provider config and run `POST /auth/sso/config/test`.
- [ ] 11.3 Complete a real browser login as a brand-new Entra ID test user
      and confirm: an account is created with the expected role (or `host`
      if unmapped), the audit log has both a creation and a login entry,
      and a second login by the same user reuses the same account.
- [ ] 11.4 Inspect the actual `groups` claim Entra ID sends for this app
      registration (GUID vs. friendly name) and record the finding in
      `docs/features/sso_authentication.md`'s Azure caveat so role-mapping
      entries are configured with the right value from day one.
