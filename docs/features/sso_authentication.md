# SSO Authentication (Staff OIDC Login)

Lets staff (Reception/Security/Host, and any tenant-defined custom role)
sign into Guestify with their company's own OIDC identity provider
(Google Workspace, Microsoft Entra ID, Okta, or any other OIDC-compliant
IdP) instead of a Guestify password — API-19. Admin signs in via
password login only, never SSO — see "Admin accounts never complete SSO
login" below. Visitor login (OTP/QR/email link, `identity_verification`)
is completely separate and untouched by this feature. See
`openspec/changes/add-sso-oidc-login/` for the proposal/design this feature
was built from, and `openspec/changes/separate-admin-staff-login/` for the
Admin/staff login-method split.

`sso` owns two tenant-scoped tables (`sso_providers`, `sso_role_mappings`)
and reuses `auth`'s existing JWT/RBAC machinery for everything else — a
successful SSO login produces the exact same access/refresh token pair,
against the exact same `User`/`Role` model, as a password login.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| GET | `/api/v1/auth/sso/config` | `sso-config:view` | — | Returns the tenant's SSO provider configuration, with the client secret masked (`****1234`). 404 if none is configured yet. |
| PUT | `/api/v1/auth/sso/config` | `sso-config:manage` | — | Creates or replaces the tenant's SSO provider configuration (display name, discovery URL, client ID, client secret). The secret is encrypted at rest and never returned in plaintext again. The discovery URL is subject to the SSRF guard below. |
| POST | `/api/v1/auth/sso/config/test` | `sso-config:manage` | — | Validates a candidate discovery URL + client ID/secret against the live IdP, without persisting anything. Always returns 200 with `{success, message}` — a failed test is not an HTTP error. Subject to the SSRF guard below. |
| GET | `/api/v1/auth/sso/role-mappings` | `sso-config:view` | — | Lists the tenant's IdP-group-claim-value → role mappings. |
| POST | `/api/v1/auth/sso/role-mappings` | `sso-config:manage` | — | Creates a mapping. 404 if the target role doesn't exist; 409 if the role is `visitor` or `admin` (Admin is never reachable via SSO — see below), or the group claim value is already mapped. |
| DELETE | `/api/v1/auth/sso/role-mappings/{id}` | `sso-config:manage` | — | Deletes a mapping (hard delete — disposable config, not audit-relevant once removed). |
| GET | `/api/v1/auth/sso/{tenant_slug}/login` | None (public) | 3/minute per IP | Redirects the browser to the tenant's configured IdP with a freshly generated `state`/`nonce`. 409 if the tenant has no enabled provider; 404 if the tenant slug doesn't exist; 503 if the IdP's discovery document can't be fetched. |
| GET | `/api/v1/auth/sso/callback` | None (public) | 3/minute per IP | The IdP's return redirect (`code`, `state` query params). Verifies everything, resolves/creates the account, and redirects to `SSO_FRONTEND_CALLBACK_URL` with a short-lived exchange `code`. Rejected (same generic error as any other callback failure) if the resolved account is an existing Admin — see "Admin accounts never complete SSO login" below. |
| POST | `/api/v1/auth/sso/exchange` | None (public) | 3/minute per IP | Redeems a single-use exchange code for the real access/refresh token pair — at least as sensitive as `POST /auth/login`, rate-limited the same way. |
| POST | `/api/v1/auth/logout` | Bearer token | — | Records a `logout` audit entry. Does **not** invalidate the token — see "Known limitations" below. |

`sso-config:manage`/`sso-config:view` are seeded into the `admin` role's
permission set alongside every other admin-only permission
(`auth/rbac_catalog.py`).

### SSRF guard on admin-supplied discovery URLs

`PUT /auth/sso/config` and `POST /auth/sso/config/test` both accept a
`discoveryUrl` the server will fetch. Before any outbound request,
`sso/oidc_client.py::_assert_safe_outbound_url` rejects a non-`https`
scheme, and rejects a URL whose host resolves to a private, loopback,
link-local, multicast, or reserved IP range — the standard mitigation
against an authenticated caller pointing the server at an internal service
or a cloud metadata endpoint. A rejected URL surfaces as `{success: false,
message: "..."}` from the test-connection endpoint, or a 503 from the
actual login flow if a previously-valid configuration's DNS later changes
to point somewhere disallowed.

## Login flow

1. Staff clicks "Sign in with `{tenant's display name}`" → browser hits
   `GET /auth/sso/{tenant_slug}/login`.
2. The app redirects to the IdP's authorization endpoint with a signed
   `state`/`nonce` pair recorded server-side (Redis, 10-minute TTL by
   default).
3. Staff authenticates at the IdP (outside this app entirely).
4. The IdP redirects back to `GET /auth/sso/callback`. The app:
   - Looks up and atomically deletes the `state` record (single-use).
   - Exchanges `code` for an ID token at the IdP's token endpoint.
   - Verifies the ID token's signature (against the IdP's published JWKS),
     issuer, audience, expiry, and `nonce` — nothing in the token is
     trusted before all of this passes.
   - Resolves the account by email: creates one just-in-time if this is
     the first login for that email in this tenant, or reuses the existing
     one otherwise.
   - Assigns a role from the tenant's IdP-group-to-role mapping table,
     defaulting to `host` if no group matches (never `admin` by default,
     no matter what).
   - Writes an audit entry (`sso_login`, plus `sso_account_created` on a
     first-time login; `sso_login_failed` on any rejection).
   - Redirects to `SSO_FRONTEND_CALLBACK_URL?code={exchange_code}` — never
     with real tokens in the URL.
5. The frontend immediately calls `POST /auth/sso/exchange` with that code
   to get the real, normal access/refresh token pair. The code is
   single-use (`SSO_EXCHANGE_CODE_TTL_SECONDS`, default 60s) and rejected
   if reused or expired.

## Role assignment is never taken from a raw IdP claim

The callback never reads a `role`/`roles` claim from the ID token and
treats it as an assignable role name. It only ever looks up the token's
`groups` claim against `sso_role_mappings`, a table only an Admin can
write to.

## Admin accounts and SSO login

By default Admin signs in via password login only (`docs/features/auth.md`) —
SSO is for every other role. A tenant can opt existing Admin accounts into
SSO by setting `allowAdminLogin: true` on `PUT /auth/sso/config` (default
`false`; returned by `GET /auth/sso/config`). It relaxes only the callback
guard below; the role-mapping guard stays, so JIT provisioning can never
create an Admin. Two guards enforce the default:

- `POST /auth/sso/role-mappings` rejects (409) any attempt to create a
  mapping targeting the `admin` role, the same way it already rejects one
  targeting `visitor`. A first-time (just-in-time provisioned) SSO login
  can therefore never be assigned Admin.
- The callback additionally rejects login (unless `allowAdminLogin` is on)
  for an **existing** account that already holds the Admin role — closing the case a role-mapping
  guard alone can't reach, since an existing account's role isn't
  re-evaluated from the token at all. The caller sees the same generic
  callback-failure response as any other rejected callback (so an
  unauthenticated caller can't use this to learn whether a given email
  belongs to an Admin account); the audit trail records the specific
  reason as `sso_login_rejected_admin_account`, distinct from the generic
  `sso_login_failed`.

**Azure Entra ID caveat**: the `groups` claim in an Entra ID token is a
list of group **object IDs (GUIDs)** by default, not the friendly names
shown in the Azure Portal, unless the app registration's token
configuration is set to emit `sAMAccountName`/NetBIOS-style group claims
(itself dependent on on-prem AD sync). `sso_role_mappings` stores and
matches whatever raw value the token actually carries, so this isn't a
functional blocker — but the value entered in a mapping must match
whatever *this* tenant's Entra ID app registration actually sends, which
should be confirmed with a real end-to-end test login before relying on
it. Also out of scope: "groups overage" (a user in 200+ AD groups gets a
`_claim_names`/`_claim_sources` indirection instead of an inline `groups`
array) — such a user simply matches no mapping and defaults to `host`.

## Config

| Setting | Default | Purpose |
|---|---|---|
| `SSO_ENCRYPTION_KEY` | unset | Fernet key (`core/encryption.py`) used to encrypt every tenant's client secret at rest. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Saving a provider config fails loudly if this is unset. |
| `SSO_REDIRECT_URI` | unset | The exact `redirect_uri` this app is registered with at every tenant's IdP (e.g. `https://api.example.com/api/v1/auth/sso/callback`). Cannot be derived from the inbound request — most OIDC providers require an exact, pre-registered match, and the `Host` header is untrusted for this purpose anyway. One fixed value works for every tenant since the tenant is carried in `state`, not the URL. |
| `SSO_FRONTEND_CALLBACK_URL` | unset | Where the callback redirects the browser with the exchange code (e.g. `https://portal.example.com/sso/callback`). |
| `SSO_EXCHANGE_CODE_TTL_SECONDS` | `60` | How long an exchange code stays redeemable. |
| `SSO_STATE_TTL_SECONDS` | `600` | How long a login attempt's `state`/`nonce` record stays valid in Redis. |
| `SSO_DEV_SEED_DISCOVERY_URL` / `SSO_DEV_SEED_CLIENT_ID` / `SSO_DEV_SEED_CLIENT_SECRET` | unset | Dev-seeding-only, see "Local Development Setup" below. |
| `SSO_DEV_SEED_DISPLAY_NAME` | `Dev SSO Provider` | Display name for the dev-seeded provider config. |

## Local Development Setup

A freshly seeded dev tenant (`scripts/seed_dev_data.py`) has **no** SSO
provider configured by default, so `GET /auth/sso/{tenant_slug}/login` will
correctly return `409 {"message": "SSO is not configured for this
tenant"}` — this is expected, not a bug (see
`sso/tests.py::test_login_initiate_without_configured_provider_returns_409`).

Seeding a fake/placeholder provider row is **not** a fix: the SSRF guard
above (`_assert_safe_outbound_url`) rejects any `discoveryUrl` that isn't a
publicly-reachable `https://` endpoint, so a local or private address saves
without error but fails at actual login time with a 503. To get a real,
clickable SSO login working locally:

1. Register a free test OIDC app with any real provider — Auth0, Okta,
   Azure AD (Entra ID), and Google Identity Platform all offer a free tier
   suitable for this. Note its discovery URL (usually
   `.well-known/openid-configuration`), client ID, and client secret.
2. Either:
   - Set `SSO_DEV_SEED_DISCOVERY_URL`, `SSO_DEV_SEED_CLIENT_ID`, and
     `SSO_DEV_SEED_CLIENT_SECRET` in `.env` (optionally
     `SSO_DEV_SEED_DISPLAY_NAME` too) and (re-)run
     `ddev exec uv run python scripts/seed_dev_data.py` — it upserts an
     enabled `SsoProvider` row for the seeded tenant automatically, safe to
     re-run if credentials change; **or**
   - Skip the env vars and call `PUT /auth/sso/config` directly (via
     Swagger or an authenticated request) with the same values — the two
     approaches produce an identical row, so use whichever fits your
     workflow.
3. Treat these three values as real credentials, exactly like
   `SSO_ENCRYPTION_KEY` — never commit them to `.env.example` with a real
   value (it stays blank there), and don't paste them into chat/logs.

## Password login (Admin only)

`POST /auth/login` (email + password, `auth` capability) is Admin's login
method, not a role-agnostic fallback: it keeps working for an Admin
account regardless of whether a tenant has SSO enabled or that tenant's
IdP is reachable — there is still always a way in for Admin, so a
misconfigured or down IdP can never lock every Admin out along with
everyone else. It is not, however, a break-glass path for staff — a
non-Admin account is rejected from this endpoint (403) even with a correct
password; SSO is that role's only login method. Its rate limit was
tightened from 5/minute to 3/minute per IP as part of the original SSO
change, since Admin login is the higher-value brute-force target once
every other role's traffic has moved to SSO (`rate-limiting` capability).

## Known limitations

- **One provider per tenant.** `sso_providers` is modeled as a table (not
  a hard singleton), so adding a second concurrently-enabled provider
  later is an additive row, not a migration — but today's endpoints only
  ever read/write "the" (singular) enabled provider.
- **SAML is not built.** Phase 2 per the product requirement — build only
  if a customer specifically needs it.
- **`POST /auth/logout` does not revoke the token.** This app issues
  stateless JWTs with no revocation list anywhere (password login
  included) — logout here only guarantees the audit entry the product
  requirement calls for. The caller's access token remains valid until it
  naturally expires (≤30 minutes).
- **No Microsoft Graph "groups overage" resolution.** See the Azure
  caveat above.
