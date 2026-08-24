## Purpose

Lets staff (Admin/Reception/Security/Host) sign into VisitorPass with their
company's own OIDC identity provider instead of a VisitorPass password,
with per-tenant provider configuration, just-in-time account provisioning,
IdP-group-to-role mapping, and full audit coverage. Visitors are never
involved — this capability governs staff sign-in only.

## ADDED Requirements

### Requirement: Per-Tenant OIDC Provider Configuration
The system SHALL let a caller with `sso-config:manage` configure exactly one
OIDC provider per tenant — an OIDC discovery URL (or issuer), a display
name, a client ID, and a client secret — and SHALL store the client secret
encrypted at rest. The system SHALL NOT return the client secret in
plaintext in any API response after it is first saved, returning a masked
value (e.g. `****1234`) instead, and SHALL NOT include the secret, encrypted
or plaintext, in any log line.

#### Scenario: Admin saves a provider configuration
- **WHEN** a caller with `sso-config:manage` submits a discovery URL,
  display name, client ID, and client secret
- **THEN** the configuration is stored with the client secret encrypted, and
  the response confirms success without echoing the secret in plaintext

#### Scenario: Reading the configuration never reveals the plaintext secret
- **WHEN** a caller with `sso-config:manage` retrieves the saved
  configuration
- **THEN** the client secret field is a masked value derived from it, never
  the plaintext or the raw encrypted bytes

#### Scenario: A caller without sso-config:manage is rejected
- **WHEN** a caller lacking `sso-config:manage` attempts to view, create, or
  update the SSO provider configuration
- **THEN** the request is rejected with 403 and nothing is changed

### Requirement: Provider Connection Can Be Tested Before Saving
The system SHALL let a caller with `sso-config:manage` validate a candidate
discovery URL and client credentials against the IdP without persisting
anything, so a configuration mistake is caught before it can lock staff out.

#### Scenario: A valid candidate configuration tests successfully
- **WHEN** a caller submits a discovery URL and client credentials that
  resolve correctly against the IdP
- **THEN** the test reports success and no SSO configuration row is created
  or modified

#### Scenario: An invalid candidate configuration fails clearly
- **WHEN** a caller submits a discovery URL or client credentials the IdP
  rejects, or a discovery URL that cannot be reached
- **THEN** the test reports failure with a caller-safe reason, and no SSO
  configuration row is created or modified

### Requirement: IdP-Group-to-Role Mapping Decides a New User's Role
The system SHALL let a caller with `sso-config:manage` maintain a per-tenant
table mapping an IdP group identifier (as it appears in the ID token's
group claim) to one existing VisitorPass role. When a new SSO user's token
carries a group that matches an entry in this table, the system SHALL
assign that role. When it carries no group that matches any entry, the
system SHALL assign the `Host` role and SHALL NOT assign `Admin` or any
other role by default under any circumstance.

#### Scenario: A mapped group assigns its configured role
- **WHEN** a first-time SSO login's ID token includes a group that matches
  a configured mapping to the `Security` role
- **THEN** the newly created account is granted the `Security` role

#### Scenario: An unmapped user defaults to Host, never Admin
- **WHEN** a first-time SSO login's ID token includes no group that matches
  any configured mapping (or no group claim at all)
- **THEN** the newly created account is granted the `Host` role

#### Scenario: A mapping can only target an existing role
- **WHEN** a caller with `sso-config:manage` attempts to create a mapping
  pointing at a role name that does not exist in the tenant's role catalog
- **THEN** the request is rejected with 404 and no mapping is created

### Requirement: SSO Login Initiation Redirects to the Tenant's Configured IdP
The system SHALL expose a public, unauthenticated endpoint that, given a
tenant identifier, redirects the browser to that tenant's configured IdP
authorization endpoint with a freshly generated, unguessable `state` value
bound server-side to this login attempt. The system SHALL reject the
request, without redirecting anywhere, when the named tenant has no
enabled SSO provider configured.

#### Scenario: A tenant with SSO enabled redirects to its IdP
- **WHEN** an unauthenticated caller starts SSO login for a tenant with an
  enabled provider configuration
- **THEN** the response redirects to that provider's authorization endpoint
  with a `state` value the system can later verify

#### Scenario: A tenant without SSO configured is rejected
- **WHEN** an unauthenticated caller starts SSO login for a tenant with no
  enabled SSO provider configured
- **THEN** the request is rejected with a clear error and no redirect occurs

### Requirement: The Callback Verifies the ID Token Before Trusting Any Claim
The system SHALL, on the IdP's return redirect, verify that the returned
`state` matches a login attempt this system generated and has not already
been consumed, and SHALL verify the ID token's signature (against the IdP's
published keys), issuer, audience, expiry, and nonce before treating any of
its claims as trustworthy. A request failing any of these checks SHALL be
rejected with a clear, generic error, and SHALL NOT create or sign into any
account.

#### Scenario: A genuine, current token is accepted
- **WHEN** the IdP redirects back with a `state` matching an unexpired,
  unconsumed login attempt and a validly signed, current, correctly
  audienced ID token
- **THEN** the callback proceeds to account resolution

#### Scenario: An unrecognized or replayed state is rejected
- **WHEN** the callback receives a `state` value that does not match any
  pending login attempt, or one already consumed by an earlier callback
- **THEN** the request is rejected and no account resolution is attempted

#### Scenario: An expired or tampered token is rejected
- **WHEN** the ID token is expired, has an invalid signature, or names an
  issuer or audience other than the configured provider and this
  application
- **THEN** the request is rejected with a clear error and no account is
  signed into

### Requirement: Just-in-Time Provisioning Resolves to Exactly One Account Per Email
The system SHALL, on a callback whose ID token has passed verification,
create a new staff account from the token's name and email on that
tenant's first login by that email, and SHALL resolve to that same existing
account (never a duplicate) on every subsequent login by the same email.

#### Scenario: A brand-new employee is provisioned automatically
- **WHEN** an email never seen before in this tenant completes SSO login
  successfully
- **THEN** a new account is created using the token's name and email, with
  no manual account creation by an Admin beforehand

#### Scenario: A returning employee reuses their existing account
- **WHEN** an email that already has an account in this tenant completes
  SSO login again
- **THEN** the login resolves to that same existing account rather than
  creating a second one

### Requirement: Tokens Are Handed to the Caller Through a Short-Lived, Single-Use Exchange
The system SHALL NOT place a long-lived access or refresh token directly in
a redirect URL. Instead, after a successful callback, the system SHALL
issue a short-lived, single-use exchange code, and SHALL only issue the
real access/refresh token pair when that exact code is redeemed once
through a dedicated exchange endpoint. A second redemption attempt of the
same code, or redemption after it has expired, SHALL be rejected.

#### Scenario: A fresh exchange code redeems successfully
- **WHEN** the caller redeems an unexpired, not-yet-used exchange code
- **THEN** the response includes a normal access/refresh token pair

#### Scenario: A reused exchange code is rejected
- **WHEN** the caller attempts to redeem an exchange code a second time
- **THEN** the second attempt is rejected and no new token pair is issued

#### Scenario: An expired exchange code is rejected
- **WHEN** the caller attempts to redeem an exchange code after its short
  validity window has passed
- **THEN** the attempt is rejected and no token pair is issued

### Requirement: Every SSO Login, Login Failure, Account Creation, and Logout Is Audited
The system SHALL write an audit log entry for every completed SSO login,
every rejected callback (invalid/expired/tampered token or state), every
just-in-time account creation, and every logout, each carrying a timestamp
and, where an account is known, the actor.

#### Scenario: A successful SSO login is audited
- **WHEN** a staff member completes SSO login successfully
- **THEN** an audit log entry recording the login exists with a timestamp
  and the account's identity

#### Scenario: A rejected callback is audited
- **WHEN** a callback is rejected for an invalid, expired, or tampered token
  or state
- **THEN** an audit log entry recording the failed attempt exists with a
  timestamp

#### Scenario: A just-in-time account creation is audited
- **WHEN** a first-time SSO login creates a new account
- **THEN** an audit log entry recording the account creation exists,
  distinct from the login entry

### Requirement: Disabling SSO or an Unreachable IdP Does Not Lock Out Staff
The system SHALL keep the existing email/password login fully functional
regardless of whether any tenant has SSO enabled, and regardless of whether
a configured IdP is reachable.

#### Scenario: Password login still works while SSO is enabled
- **WHEN** a tenant has SSO enabled and configured
- **THEN** an existing staff member can still authenticate via
  `POST /auth/login` with their email and password

#### Scenario: An unreachable IdP does not block password login
- **WHEN** a tenant's configured IdP is unreachable
- **THEN** `POST /auth/login` is unaffected and continues to authenticate
  valid credentials normally
