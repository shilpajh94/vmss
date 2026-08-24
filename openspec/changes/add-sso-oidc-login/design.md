## Context

See `proposal.md` - Why/What Changes for motivation and scope. Relevant
existing state this design builds on:

- `auth/service.py::create_user` already does everything JIT provisioning
  needs — creates the `User` row, writes the global `tenant_user_index`
  entry, and accepts `(role, branch_id)` grants — in one transaction. This
  change reuses it rather than duplicating account-creation logic.
- `core/security.py::_create_token`/`decode_token` is the existing PyJWT
  helper, HS256 only, used today for internally-issued access/refresh/
  platform/identity-verified tokens. Verifying an externally-issued Azure AD
  ID token needs RS256 against a rotating JWKS — a different trust model
  from anything `core/security.py` does today (verifying a token *we*
  signed vs. one a third party signed).
- `identity_verification` is the closest existing analog for "short-lived,
  Redis-or-JWT-backed proof consumed exactly once by a dedicated endpoint" —
  its `create_identity_verified_token`/verify pattern is reused conceptually
  for this change's exchange code, not its code directly (different claims,
  different consumer).
- `core/rate_limit.py::limiter` is slowapi, Redis-backed, already applied to
  `POST /auth/login` at `5/minute` (`auth/router.py:48`).
- No existing module encrypts a database column. `argon2-cffi` (password
  hashing) is one-way and unsuitable for a secret we must later decrypt to
  call the IdP's token endpoint.
- `httpx` and `cryptography` are not runtime dependencies today — `httpx` is
  dev-only (tests drive the ASGI app via `httpx.AsyncClient`); `pyjwt` has
  never needed `cryptography` because every token this app issues and
  verifies today is HS256 (symmetric, no `cryptography` backend required).

## Goals / Non-Goals

**Goals:**
- A working OIDC login flow (initiate → IdP → callback → exchange) usable
  against Microsoft Entra ID today (the provisioned app registration for
  this rollout), and against any other OIDC-compliant IdP (Google
  Workspace, Okta) without provider-specific code — OIDC discovery + JWKS
  is uniform across compliant providers.
- Access/refresh tokens never appear in a browser-visible URL, redirect
  history, or server access log.
- The client secret is encrypted at rest with a real, general-purpose
  mechanism other tenant-schema secrets can reuse later (not a one-off
  SSO-specific hack).

**Non-Goals:**
- SAML (explicit Phase 2 in the docx; not started here).
- Token revocation/blacklisting for the new `POST /auth/logout` endpoint.
  This app issues stateless JWTs with no revocation list anywhere today
  (password login included) — adding one is a separate, larger change.
  `POST /auth/logout` in this change only writes the audit entry the docx's
  acceptance checklist requires; the access token remains valid until it
  naturally expires (≤30 minutes, per `access_token_expire_minutes`).
- Multiple concurrently-enabled IdPs per tenant. One `SsoProvider` row per
  tenant, matching the docx's singular "a settings screen."
  Multi-IdP-per-tenant is a plausible future request, not asked for here.
- Resolving Microsoft Graph `/me/memberOf` for the "groups overage" case
  (a user in 200+ AD groups gets `_claim_names`/`_claim_sources` indirection
  markers in the token instead of an inline `groups` array). Such a user
  simply matches no mapping and defaults to `Host`, which is a safe (if
  under-privileged) outcome, not a security gap. Flagged as a fast-follow
  if a customer hits it.
- A per-tenant frontend redirect URL. Only one deployment of the React
  portal exists; its callback URL is one global setting
  (`SSO_FRONTEND_CALLBACK_URL`), not a per-tenant column. Revisit if/when a
  tenant needs its own portal domain.

## Decisions

### New `src/vmss_api/sso/` feature package
`router.py`, `service.py`, `schemas.py`, `models.py`, `repository.py`,
`oidc_client.py`, `tests.py` — follows `fastapi-architecture.md` §1
exactly. `oidc_client.py` isolates all outbound HTTP to the IdP (discovery
document fetch, JWKS fetch/cache, authorization-code-for-tokens exchange)
behind a small interface, so `tests.py` can substitute a fake/`respx`-mocked
client instead of hitting a real IdP in CI.

**Alternative considered**: fold this into `auth/`. Rejected — `auth/` is
already the largest feature package (users, roles, RBAC, audit) and none of
its existing files need to change for the OIDC mechanics themselves (only
`router.py`'s rate limit and a new `/logout` route, and `service.py` gains a
thin JIT-provisioning wrapper around the already-exported `create_user`).
Keeping SSO's own config/flow/tests in one place matches how
`identity_verification` was split out from `invitations` for the same
reason.

### Two new tenant-scoped tables
```python
class SsoProvider(Base, TimestampMixin):
    __tablename__ = "sso_providers"
    id: Mapped[uuid.UUID]
    display_name: Mapped[str]  # shown on "Sign in with {display_name}"
    discovery_url: Mapped[str]  # e.g. Entra ID's /v2.0/.well-known/openid-configuration
    client_id: Mapped[str]
    client_secret_encrypted: Mapped[str]  # Fernet ciphertext, base64
    is_enabled: Mapped[bool]


class SsoRoleMapping(Base, TimestampMixin):
    __tablename__ = "sso_role_mappings"
    id: Mapped[uuid.UUID]
    idp_group_claim_value: Mapped[str]  # UniqueConstraint per tenant
    role_id: Mapped[uuid.UUID]  # FK roles.id
```
Both are `Base` (tenant-scoped by schema, not a column — `database-architecture.md`
§2), one row per config item, migrated once in `alembic_tenant/versions/`
and applied to every tenant at provisioning like every other tenant table.
`SsoProvider` is modeled as a small table (not a single-row upsert
constrained by app logic to exactly one), so a future SAML/second-provider
change is an additive row, not a schema change — `router.py` exposes it as
a singular `GET/PUT /auth/sso/config` today because the docx's settings
screen is singular, but nothing here blocks adding `POST` for a second
provider later without a migration.

### `core/encryption.py`: Fernet, not a per-feature ad hoc scheme
A new core module, `encrypt(plaintext: str) -> str` / `decrypt(ciphertext:
str) -> str`, backed by `cryptography.fernet.Fernet` keyed from a new
`SSO_ENCRYPTION_KEY` setting (a base64 urlsafe 32-byte key, generated once
per environment via `Fernet.generate_key()`, stored in `.env` like every
other secret per `security-architecture.md` §3). This lives in `core/`
(not `sso/`) because encrypting a DB column is general infrastructure, and
the docx itself frames future-proofing ("encrypt at rest") as a standing
expectation, not a one-off — a future feature needing the same guarantee
(e.g. an SMTP relay password, a webhook signing secret) reuses this instead
of inventing its own.

**Alternative considered**: `argon2-cffi` (already a dependency). Rejected
outright — Argon2 is a one-way hash; the client secret must be *recovered*
in plaintext to call the IdP's token endpoint, which a hash can never do.

### Verifying externally-issued tokens: PyJWT's `PyJWKClient`, not a new library
`pyjwt>=2.13.0` (already a dependency) ships `PyJWKClient`, which fetches
and caches an IdP's JWKS by URL and returns the correct signing key for a
given token's `kid` header. Combined with `jwt.decode(id_token, signing_key,
algorithms=["RS256"], audience=client_id, issuer=issuer)`, this covers
signature, issuer, audience, and expiry verification with no new JWT
library. `cryptography` becomes a real dependency here (it's PyJWT's RS256
backend) — previously never installed because every token this app itself
issues is HS256.

**Alternative considered**: `authlib`, which bundles OIDC-specific
convenience (discovery parsing, nonce handling) beyond raw JWT. Rejected for
this change's scope — the amount of glue code `authlib` would save is
small (discovery is one HTTP GET + JSON parse; nonce is one extra claim
compared against a value already being tracked for the exchange flow), and
adding it means learning/auditing a second JWT/OIDC library's trust
decisions in a security-sensitive path, versus building directly on the
`pyjwt` verification behavior already relied on and understood everywhere
else in this codebase. Revisit if Phase 2's SAML work needs a
comprehensive federation library anyway.

### `httpx` promoted to a runtime dependency
`oidc_client.py` needs an async HTTP client for the discovery-document
fetch and the authorization-code-for-tokens POST to the IdP. `httpx` is
already used everywhere in `tests.py` via `httpx.AsyncClient` against the
app's ASGI transport, so promoting it (moving the line from
`[dependency-groups].dev` to `[project].dependencies` in `pyproject.toml`)
adds no new library to the dependency tree, only a new runtime use of one
already vetted and pinned.

### Tenant resolution for the public initiate endpoint: `tenant.slug`, not `tenant_id`
`GET /auth/sso/{tenant_slug}/login` resolves the tenant from
`Tenant.slug` (already a public-ish, non-secret identifier —
`database-architecture.md` §2) to decide which provider config to redirect
to. This does not violate `security-architecture.md` §1's "`tenant_id` is
never read from a request... and trusted" rule: that rule protects
*authorization* decisions (which schema's data a request can touch) — this
lookup only selects which public "Sign in with X" redirect target to use,
the equivalent of choosing which company's login button was clicked. No
tenant-scoped data is read here, and the eventual session's real
`tenant_id` claim is derived server-side from the `state` record the
callback looks up, never re-read from anything client-supplied at that
point (see the exchange-code decision below).

**Alternative considered**: resolve tenant via `settings.default_tenant_slug`
only, matching `invitations/deps.py::track_default_tenant_db`'s pattern for
today's single-tenant reality. Rejected — `project-rules.md` explicitly
warns against code that assumes there's only ever one tenant, and a path
param costs nothing extra here.

### Exchange code, not tokens-in-a-redirect
The callback, after verifying the ID token, does not redirect the browser
straight to the frontend with access/refresh tokens. It mints a short-lived
(60s), single-use, HS256-signed exchange token (`core/security.py`-style,
new `type: "sso_exchange"` claim, `jti` claim for replay detection) and
redirects to `{SSO_FRONTEND_CALLBACK_URL}?code={exchange_token}`. The
frontend immediately calls `POST /auth/sso/exchange` with that code, which
verifies the JWT, atomically marks its `jti` consumed in Redis
(`vmss:{tenant_id}:sso:exchange:{jti}`, `SETNX` + a TTL matching the token's
remaining life — a second `SETNX` on the same key fails, which is the
single-use check), and only then calls `auth/service.py::issue_tokens` for
the real pair.

**Alternative considered**: encode `state`/session data entirely in Redis
(mirroring `identity_verification`'s OTP pattern) instead of a signed JWT.
Rejected — the exchange code needs to travel through a URL query param the
same way `state` does for the outbound leg, and a signed, self-contained
JWT means the exchange endpoint can verify it without a prior Redis lookup
race; Redis is still used, but only for the single-use marker, which is
exactly what Redis's atomic `SETNX` is for.

### Role assignment only ever comes from the curated mapping table
The callback never reads a `role`/`roles` claim from the ID token directly
as an assignable role name. It reads whatever `groups` claim the token
actually carries (a GUID or a friendly name, depending on how the tenant's
Azure AD app registration is configured — see Risks below) and looks it up
against `SsoRoleMapping`, which only ever contains rows an Admin explicitly
created. This is what satisfies the docx §9 rule ("don't automatically
trust a role claim from the IdP... it's safer to have an Admin confirm/
upgrade sensitive roles") without blocking legitimate Admin-curated
`Admin`-role mappings: the trust boundary is "an Admin decided this IdP
group means this role," not "the IdP said so."

### `state`/exchange Redis keys are NOT tenant-prefixed — a deliberate exception
Added during implementation: `database-architecture.md` §6's
`vmss:{tenant_id}:{feature}:...` key convention assumes the tenant is
already known when the key is built. The `state` record is the one place
that's circular — the callback receives only `code` and `state`, with no
tenant identifier at all, and resolving the tenant is exactly what looking
up that record accomplishes. Its key is therefore `vmss:sso:state:{state}`
(and the exchange marker `vmss:sso:exchange:{jti}`), with `tenant_id` stored
as a *field inside* the hash instead of in the key path. This is safe
without a tenant segment because `state`/`jti` are each a 256-bit random
token (`secrets.token_urlsafe(32)`) — unguessable and already globally
unique — so there is no realistic collision or enumeration risk a tenant
prefix would have prevented; the tenant-prefix convention exists to keep
*intentional* per-tenant namespacing tidy, not to add entropy a random
token doesn't already have.

### Fixed `redirect_uri`, not derived from the request
Added during implementation (not foreseen when this design was first
written): the authorization request's `redirect_uri` must exactly match
what's pre-registered on the IdP side — Microsoft Entra ID (and most OIDC
providers) reject a mismatch outright. It cannot be built from the inbound
request's `Host`/`X-Forwarded-Host` header, which is client-controlled and
exactly the kind of untrusted input `security-architecture.md` warns
about. `SSO_REDIRECT_URI` is therefore a new, fixed global setting (one
value, not per-tenant — the callback route itself is tenant-agnostic since
the tenant is carried in `state`, not the URL).

### Failure-path audit writes are synchronous, not backgrounded
Discovered during implementation: `background_tasks.add_task(...)` called
immediately before `raise HTTPException(...)` never actually runs. FastAPI
only attaches an endpoint's `BackgroundTasks` instance to the `Response`
object that endpoint itself returns; when an `HTTPException` propagates out
instead, `core/middleware.py::http_exception_handler` builds an entirely
separate `error_response(...)` with no knowledge of the original
`BackgroundTasks`, so anything scheduled on it is silently dropped — a
route-wide behavior, not specific to `sso/`. Every other existing route only
ever calls `background_tasks.add_task` right before a successful `return`,
so this gap was never hit before. `sso/service.py::handle_callback`'s two
`sso_login_failed` audit writes are therefore `await record_audit_log(...)`
directly (synchronous) rather than backgrounded — acceptable here since the
request is already failing (a few extra milliseconds on an error response
is a non-issue), and it's what makes spec.md's "A rejected callback is
audited" requirement actually true rather than silently a no-op. The
success-path writes (`sso_login`, `sso_account_created`) stay backgrounded,
since those precede a normal `return` and are unaffected by this gap.

### New permission codes
`sso-config:manage` and `sso-config:view`, following the existing
`<resource>:manage`/`<resource>:view` pairing in `auth/rbac_catalog.py`.
Seeded into the `admin` role's permission set alongside the rest of
`PERMISSION_CODES`, same as every other admin-only capability added so far.

## Risks / Trade-offs

- **[Risk]** Azure AD's `groups` claim in an ID token is a list of group
  *object IDs* (GUIDs) by default, not the friendly names shown in the
  Azure Portal, unless the app registration's token configuration is set to
  emit `sAMAccountName`/`NetBIOS`-style group claims (itself dependent on
  on-prem AD sync being in place). → **Mitigation**: `SsoRoleMapping` stores
  and matches whatever raw string value the token actually carries — the
  system is agnostic to GUID-vs-name. Document in the admin-facing setup
  guide that the value entered in the mapping table must match Azure's
  actual claim output for *this* tenant's app registration, verified once
  by an end-to-end test login (inspect the resulting account's assigned
  role, or the audit log entry for that login) — not something this design
  can guarantee at configuration-save time without customer-specific Azure
  configuration.
- **[Risk]** Tightening `POST /auth/login` from 5/minute to 3/minute is a
  breaking change to the `rate-limiting` spec's documented scenario and to
  any existing test asserting the old threshold. → **Mitigation**: tracked
  explicitly in `proposal.md` as **BREAKING**; `tasks.md` includes updating
  the existing rate-limit test alongside the `auth/router.py` change so
  they land in the same commit, not a follow-up.
- **[Risk]** `PyJWKClient` caches signing keys in-process; if Azure AD
  rotates its signing key at the exact moment a token using the new key
  arrives, the first request could fail verification. → **Mitigation**:
  `PyJWKClient`'s built-in cache already handles this by re-fetching on a
  `kid` cache miss before failing — no extra code needed, just don't wrap it
  in a longer-lived custom cache that would suppress that re-fetch.
- **[Trade-off]** A single `SsoProvider` row per tenant (Non-Goals) means a
  customer wanting Google *and* Microsoft simultaneously isn't supported
  yet. Accepted per the docx's singular "a settings screen" framing; the
  table shape doesn't block adding it later.

## Migration Plan

1. Add `sso_providers` and `sso_role_mappings` to `alembic_tenant/versions/`
   as one new revision (both tables are introduced together, always
   deployed together — no reason to split).
2. Add `sso-config:manage`/`sso-config:view` to `auth/rbac_catalog.py`'s
   `PERMISSION_CODES` and the `admin` role's grant list — existing tenants
   pick these up the next time `alembic upgrade head` runs against their
   schema (permissions are global-schema rows; the grant is a tenant-schema
   `role_permissions` row seeded by the same tenant migration/upgrade path
   `platform/service.py::create_tenant` already uses for every other
   permission added to the catalog after initial provisioning).
3. Ship with SSO disabled by default (`SsoProvider` table starts empty,
   `is_enabled` has no rows to be `True`) — no tenant is affected until an
   Admin explicitly configures and enables a provider. Rollback is simply
   not enabling it / disabling `is_enabled` on an existing row; the
   password login path is never touched by this toggle.
4. Roll out the tightened `POST /auth/login` rate limit in the same
   deployment as everything else — it's a one-line `@limiter.limit(...)`
   change with no data migration, and per the docx it's specifically meant
   to take effect as SSO becomes available, not lag behind it.
