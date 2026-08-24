## MODIFIED Requirements

### Requirement: JWT-Based Authentication
The system SHALL authenticate users via short-lived JWT access tokens and
longer-lived refresh tokens, issued only after either (a) password
verification against an Argon2 hash, or (b) a fully verified SSO identity
assertion (`sso-authentication` capability: signature, issuer, audience,
expiry, nonce, and state all checked before any claim is trusted). The
system SHALL reject any token that is expired, malformed, or signed with
the wrong key. A user account created just-in-time by a successful SSO
login is a normal `User` row and is subject to every existing RBAC and
branch-scoping rule exactly as an account created any other way.

#### Scenario: Successful login issues a token pair
- **WHEN** a caller submits valid email/password credentials to
  `POST /auth/login`
- **THEN** the response includes an access token and a refresh token, and the
  access token's claims include the caller's `tenant_id`

#### Scenario: Successful SSO login issues a token pair
- **WHEN** a caller completes SSO login and redeems its exchange code
  (`sso-authentication` capability)
- **THEN** the response includes an access token and a refresh token
  carrying the same claims a password login would produce, and the
  underlying account is subject to the same RBAC/branch-scoping checks as
  any other user

#### Scenario: Expired or invalid token is rejected
- **WHEN** a request presents an expired, tampered, or wrong-type (e.g. a
  refresh token used where an access token is required) bearer token
- **THEN** the request is rejected with 401 and no tenant/user resolution is
  attempted
