# Registrations Specification

## Purpose

Lets a visitor who arrives without a prior invitation register themselves
on-site from the app, using the same visit-record contract the staff
pre-registration flow already uses, without requiring a staff bearer token.

## Requirements

### Requirement: Walk-in registration accepts the same visit-record contract as staff pre-registration
`POST /api/v1/registrations/walk-in` SHALL accept the identical JSON payload
shape used by invitation creation (`registrationType`, `primaryContact`,
`visitors`, `visitDetails`, `carriedItems`, `vehicles`, `consents`), including
its existing cross-field rules: an `individual` registration MUST NOT list
additional visitors, a `group` registration MUST list at least one, every
contact/visitor entry MUST supply at least one of email/phone, and all three
consent flags MUST be accepted. Each visitor (including the primary contact)
submits their own ID-proof file, matched by order.

#### Scenario: Individual walk-in registration
- **WHEN** a visitor submits a `registrationType: "individual"` payload with
  a primary contact, visit details, consents, and one ID-proof file
- **THEN** the system creates the registration and returns a tracking ID and
  status, the same response shape `POST /invitations` returns

#### Scenario: Group walk-in registration
- **WHEN** a visitor submits a `registrationType: "group"` payload with a
  primary contact, one or more co-visitors each with their own ID-proof
  file, visit details, and consents
- **THEN** the system creates the registration with every listed visitor
  attached

#### Scenario: Visitor list does not match registration type
- **WHEN** an `individual` payload lists co-visitors, or a `group` payload
  lists none
- **THEN** the request is rejected with a validation error, identical to
  today's invitation-creation behavior

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

### Requirement: Walk-in registration is rate-limited
As a public, unauthenticated-by-user write endpoint, `POST
/registrations/walk-in` SHALL be rate-limited per the same posture as other
public visitor-facing endpoints (`security-architecture.md` §2).

#### Scenario: Requests within the limit succeed
- **WHEN** a device stays under the configured rate limit
- **THEN** each request is processed normally

#### Scenario: Requests over the limit are rejected
- **WHEN** a device exceeds the configured rate limit
- **THEN** the system rejects further requests with 429 until the window
  resets

### Requirement: A walk-in registration is distinguishable from a staff pre-registration
Every created registration SHALL record which channel created it (staff
pre-registration vs. visitor walk-in). A walk-in registration SHALL have no
associated staff creator.

#### Scenario: Walk-in registration has no staff creator
- **WHEN** a registration is created via `POST /registrations/walk-in`
- **THEN** the stored record's creating channel is "visitor walk-in" and it
  has no associated staff user

#### Scenario: Staff pre-registration is unaffected
- **WHEN** a registration is created via the existing `POST /invitations`
  (employee, bearer token)
- **THEN** the stored record's creating channel is "staff pre-registration",
  matching today's behavior with no observable change to that endpoint

### Requirement: Walk-in registration creates a record only, not a check-in
Creating a walk-in registration SHALL NOT mark a visitor as checked in and
SHALL NOT issue a badge. It produces the same kind of record pre-registration
does (a tracking ID and status), available for reception/security to act on
separately.

#### Scenario: Response contains no check-in state
- **WHEN** a walk-in registration is created successfully
- **THEN** the response contains a tracking ID and status only — no badge,
  check-in time, or access-grant information, since none has been issued

### Requirement: Walk-in registration submissions support retried requests without duplication
The endpoint SHALL accept an `Idempotency-Key` header. A retried request
carrying the same key SHALL return the original response instead of creating
a second registration.

#### Scenario: Retried submission with the same idempotency key
- **WHEN** a device retries a walk-in registration request with the same
  `Idempotency-Key` as an earlier successful request
- **THEN** the system returns the original response and does not create a
  second registration record

### Requirement: Walk-in registration is audited
Creating a walk-in registration SHALL be recorded in the tenant's audit
trail, consistent with `security-architecture.md` §5, with no actor user
recorded (since none is authenticated).

#### Scenario: Audit entry recorded with no actor
- **WHEN** a walk-in registration is created
- **THEN** an audit log entry is written for the creation action, with no
  actor user, tied to the resolved tenant and branch

### Requirement: Walk-in Registration Enforces the Server-Resolved Branch's Form-Builder Configuration
A walk-in registration's required fields, allowed custom-field keys/options,
and consent keys SHALL be validated against the published form-builder
configuration of the branch the server itself resolves (via device
credential, or the default-tenant/default-branch fallback) — never against
a branch a client may have separately assumed or rendered. WHEN a submitted
registration is rejected because it does not match the server-resolved
branch's configuration, the system SHALL log which branch was enforced, so
a client/server branch divergence is distinguishable in the log from any
other validation failure.

#### Scenario: Submission is validated against the server-resolved branch, not a client-assumed one
- **WHEN** a walk-in registration is submitted, and the server resolves a
  branch (by device credential or default-tenant/default-branch fallback)
- **THEN** the submission's required fields, custom-field keys/options, and
  consent keys are validated against that resolved branch's published
  form-builder configuration, regardless of which branch's configuration
  the submitting client fetched or rendered

#### Scenario: A configuration mismatch is logged with the enforced branch
- **WHEN** a walk-in registration is rejected for a required-field, custom-
  field, or consent-key mismatch against the server-resolved branch's
  configuration
- **THEN** the rejection is logged with the resolved branch's id, so an
  operator can tell from the log whether the submitting client was
  rendering a different branch's configuration
