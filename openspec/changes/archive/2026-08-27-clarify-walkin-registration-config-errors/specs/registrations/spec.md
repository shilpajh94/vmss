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

When rejecting a request for lacking a usable device credential, the system
SHALL distinguish two causes in its response and log output:
- The caller presented a device credential that does not resolve to an
  active, provisioned device (or resolves to an inactive tenant/branch) —
  a client-side error.
- The caller presented no device credential, and the server-configured
  default tenant or default branch does not exist or is inactive — a
  server-side misconfiguration, not a property of the caller's request.

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

#### Scenario: Invalid device credential is reported and logged as a client-side anomaly
- **WHEN** a request carries a device credential that does not resolve to
  an active, provisioned device, or that resolves to an inactive tenant or
  branch
- **THEN** the 401 response message indicates the device credential itself
  is invalid
- **AND** the rejection is logged at `WARNING`, consistent with
  `logging-observability.md` §3's treatment of client-side anomalies

#### Scenario: Unconfigured default tenant/branch is reported and logged as a server misconfiguration
- **WHEN** a request is made with no device credential, and the
  server-configured default tenant or default branch does not exist or is
  inactive
- **THEN** the 401 response message is distinct from the invalid-credential
  case and indicates the service is not configured for the environment
- **AND** the rejection is logged at `ERROR`, consistent with
  `logging-observability.md` §3's "needs a human to look" bar, since this
  is a server-side configuration gap and not caused by anything the caller
  sent
- **AND** the `ERROR` log distinguishes, per entity (default tenant vs.
  default branch), whether the cause was that no such row exists at all
  versus that the row exists but is inactive — so an operator can tell
  from the log alone whether the fix is provisioning a missing tenant/branch
  or re-activating an existing one, without reading source

#### Scenario: Valid device credential resolves tenant and branch
- **WHEN** a request carries a device credential provisioned for a specific
  branch
- **THEN** the registration is created against that branch's tenant schema,
  regardless of any other value the client may have sent, and regardless of
  what the default tenant/branch are configured as
