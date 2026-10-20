## MODIFIED Requirements

### Requirement: IdP-Group-to-Role Mapping Decides a New User's Role
The system SHALL let a caller with `sso-config:manage` maintain a per-tenant
table mapping an IdP group identifier (as it appears in the ID token's
group claim) to one existing Guestify role, except the Admin role, which
SHALL NOT be a valid mapping target. When a new SSO user's token carries a
group that matches an entry in this table, the system SHALL assign that
role. When it carries no group that matches any entry, the system SHALL
assign the `Host` role and SHALL NOT assign `Admin` or any other role by
default under any circumstance.

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

#### Scenario: A mapping targeting the Admin role is rejected
- **WHEN** a caller with `sso-config:manage` attempts to create a mapping
  pointing at the Admin role
- **THEN** the request is rejected with 409, the same way a mapping
  targeting the Visitor role is rejected, and no mapping is created

## ADDED Requirements

### Requirement: An Admin Account Cannot Complete SSO Login
The system SHALL reject an SSO callback that resolves, by email, to an
existing account holding the Admin role — Admin accounts authenticate
exclusively through password login (`auth` capability). The rejection
SHALL use the same generic, caller-facing error as any other rejected
callback (invalid/expired token or state), so an unauthenticated caller
cannot use this endpoint to learn whether a given email belongs to an
Admin account. The rejection SHALL still be distinguishable from other
callback failures in the audit trail.

#### Scenario: An existing Admin account is rejected at callback
- **WHEN** an SSO callback's verified ID token resolves by email to an
  existing account that holds the Admin role
- **THEN** the callback is rejected with the same generic error as any
  other invalid callback, no exchange code is issued, and no tokens are
  ever produced for that login attempt

#### Scenario: The rejection is distinguishable in the audit trail
- **WHEN** an SSO callback is rejected because the resolved account holds
  the Admin role
- **THEN** an audit log entry distinct from a generic `sso_login_failed`
  entry records that the rejection was specifically because the account is
  an Admin account
