## MODIFIED Requirements

### Requirement: Walk-in registration is authenticated by a device credential, not a user
The endpoint SHALL NOT require or accept a staff bearer token. It MAY be
presented a device credential via a request header; when present, the
system SHALL resolve it server-side to exactly one tenant and one branch.
When no device credential is presented, the system SHALL instead resolve
the request against a single server-configured default tenant and default
branch. The request payload SHALL NOT contain a tenant or branch
identifier, and any such value, if present, is never trusted for
tenant/branch resolution.

#### Scenario: No device credential falls back to the default tenant and branch
- **WHEN** a request is made with no device credential, and the
  server-configured default tenant and default branch both exist and are
  active
- **THEN** the registration is created against the default tenant's schema
  and default branch, and the request is not rejected for lacking a
  credential

#### Scenario: Missing or invalid device credential
- **WHEN** a request carries a device credential that does not resolve to
  an active, provisioned device, **OR** a request is made with no device
  credential and the server-configured default tenant or default branch
  does not exist or is inactive
- **THEN** the system rejects the request with 401 and does not create a
  registration

#### Scenario: Valid device credential resolves tenant and branch
- **WHEN** a request carries a device credential provisioned for a specific
  branch
- **THEN** the registration is created against that branch's tenant schema,
  regardless of any other value the client may have sent, and regardless of
  what the default tenant/branch are configured as
