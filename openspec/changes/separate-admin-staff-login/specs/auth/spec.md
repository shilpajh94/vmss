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

Password login (`POST /auth/login`) SHALL succeed only for a caller whose
account holds the Admin role (at any branch or company-wide). A caller
with valid credentials but no Admin role grant SHALL be rejected with 403
and a message directing them to their organization's SSO login, without
revealing whether the rejection was for that reason versus another. Every
other role (Reception, Security, Host, and any tenant-defined custom role)
SHALL authenticate exclusively through the `sso-authentication` capability;
this system SHALL provide no password-based path for those roles.

#### Scenario: Successful login issues a token pair
- **WHEN** a caller holding the Admin role submits valid email/password
  credentials to `POST /auth/login`
- **THEN** the response includes an access token and a refresh token, and
  the access token's claims include the caller's `tenant_id`

#### Scenario: Successful SSO login issues a token pair
- **WHEN** a caller completes SSO login and redeems its exchange code
  (`sso-authentication` capability)
- **THEN** the response includes an access token and a refresh token
  carrying the same claims a password login would produce, and the
  underlying account is subject to the same RBAC/branch-scoping checks as
  any other user

#### Scenario: A non-Admin account is rejected from password login
- **WHEN** a caller whose account holds no Admin role grant submits
  correct email/password credentials to `POST /auth/login`
- **THEN** the request is rejected with 403, no token pair is issued, and
  the response does not confirm whether the credentials themselves were
  otherwise valid

#### Scenario: Expired or invalid token is rejected
- **WHEN** a request presents an expired, tampered, or wrong-type (e.g. a
  refresh token used where an access token is required) bearer token
- **THEN** the request is rejected with 401 and no tenant/user resolution is
  attempted
