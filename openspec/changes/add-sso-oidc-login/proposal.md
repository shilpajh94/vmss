## Why

API-19 (Admin/Platform: SSO integration). Staff (Admin/Reception/Security/Host)
currently have exactly one way into VisitorPass: email + password
(`auth/service.py::authenticate_user`). Per
`Requirements/staff VMS/staff-sso-login.pdf` and
`SSO_Login_Requirement_Simple (1).docx`, enterprise customers expect staff to
sign in with the same corporate identity they already use for email
(Google Workspace / Microsoft Entra ID / Okta), and expect access to disappear
automatically the moment IT disables that account — neither of which a local
password can do. This change adds that path for staff only; the visitor OTP/
QR/email-link login (`identity_verification`) is explicitly untouched.

The docx scopes Phase 1 to OIDC (the protocol most IdPs, including the
Microsoft Entra ID app registration already provisioned for this rollout,
speak natively) and defers SAML to a later change, only if a customer
specifically requires it.

## What Changes

- New per-tenant SSO configuration: an Admin (`sso-config:manage`) enters one
  OIDC provider's discovery URL, client ID, and client secret through an
  admin settings endpoint; the secret is encrypted at rest and never
  returned in plaintext after the initial save (masked as `****1234`
  thereafter). An optional "test connection" endpoint validates the
  discovery document and credentials without persisting anything.
- New per-tenant IdP-group → VisitorPass-role mapping table
  (`sso-config:manage`), used to decide a brand-new SSO user's role.
  Unmapped users default to `Host` (never `Admin`) — an Admin upgrades them
  manually afterward, per the docx's Section 7 rule.
- New public (pre-authentication) OIDC login flow: initiate → redirect to the
  tenant's IdP → callback → verify the ID token (signature, issuer,
  audience, expiry, nonce) → a short-lived, single-use exchange step that
  hands the browser real access/refresh tokens without ever putting them in
  a URL or browser history.
- **Just-in-time (JIT) provisioning**: a first-time SSO login auto-creates a
  `User` row from the ID token's name/email claims and assigns a role via
  the mapping table above — no Admin has to pre-create the account.
  Returning users resolve to their existing account, not a duplicate.
- Every SSO login, login failure, JIT account creation, and logout is written
  to the existing tenant `AuditLog`, matching how other mutating actions are
  audited (`security-architecture.md` §5).
- Existing email+password login (`POST /auth/login`) is kept fully
  functional as the break-glass path when SSO is disabled or the IdP is
  unreachable, and its rate limit is tightened from 5/minute to 3/minute per
  IP now that it becomes the higher-value target once SSO is the default
  path in (docx Section 9). **BREAKING** for any existing caller retrying
  password login faster than 3/minute (the `rate-limiting` capability's
  documented threshold for `POST /auth/login`).
- A new minimal `POST /auth/logout` endpoint is added so a logout event has
  somewhere to be audited — it records the audit entry only; VMSS_API issues
  stateless JWTs with no revocation list today, so this does not add token
  invalidation (tracked as a non-goal in `design.md`).
- Not in scope: SAML support (explicit Phase 2 in the docx — build only if a
  customer requires it), a second concurrently-enabled IdP per tenant,
  Microsoft Graph group-membership resolution for tenants with 200+ AD
  groups ("groups overage"), and any change to the visitor-facing login
  flow.

## Capabilities

### New Capabilities
- `sso-authentication`: per-tenant OIDC provider configuration (encrypted
  client secret, connection test), the login-initiate/callback/token-exchange
  flow, ID-token verification, JIT user provisioning, IdP-group-to-role
  mapping, and audit logging for SSO login/logout/account-creation events.

### Modified Capabilities
- `auth`: the "JWT-Based Authentication" requirement currently ties token
  issuance strictly to Argon2 password verification; it is widened to also
  cover issuance after a successful, fully-verified SSO identity assertion,
  and to state that a JIT-provisioned user is a normal `User` row subject to
  every existing RBAC/branch-scoping rule.
- `rate-limiting`: the "Tenant-user login is rate-limited" scenario's
  documented threshold for `POST /auth/login` tightens from "more than 5
  requests per minute" to "more than 3 requests per minute".

## Impact

- **New code**: `src/vmss_api/sso/` (`router.py`, `service.py`, `schemas.py`,
  `models.py`, `repository.py`, `oidc_client.py`, `tests.py`).
- **New core module**: `src/vmss_api/core/encryption.py` (Fernet-based
  encrypt/decrypt for the client secret column — no existing utility in the
  codebase encrypts a DB column today).
- **Changed**: `auth/router.py` (`/auth/login` rate limit; new
  `/auth/logout`), `auth/service.py` (JIT provisioning reuses `create_user`),
  `core/config.py` / `.env.example` (new SSO + encryption-key settings),
  `src/vmss_api/api.py` (register `sso.router.router`), `main.py`
  (`_TAGS_METADATA`), `alembic_tenant/versions/` (two new tenant-schema
  tables: `sso_providers`, `sso_role_mappings`), `pyproject.toml` (promote
  `httpx` to a runtime dependency for calling the IdP's token endpoint; add
  `cryptography` for Fernet + RS256 JWKS verification; add dev-only `respx`
  for mocking IdP HTTP calls in tests).
- **Credentials**: the Microsoft Entra ID app registration details supplied
  for this rollout (tenant/client ID, client secret) are configuration data
  for the "test connection" and end-to-end verification steps in
  `tasks.md` — they are never written into a proposal/design/tasks file or
  committed to the repo; they belong in a local `.env`/the admin settings
  screen only, per `security-architecture.md` §3.
