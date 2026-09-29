## MODIFIED Requirements

### Requirement: Walk-in registration accepts the same visit-record contract as staff pre-registration
`POST /api/v1/registrations/walk-in` SHALL accept the identical JSON payload
shape used by invitation creation (`registrationType`, `primaryContact`,
`visitors`, `visitDetails`, `carriedItems`, `vehicles`, `consents`), plus the
same admin-authored `customFields`/`groups` answer arrays invitation
creation accepts at each matching scope — per visitor entry
(`primaryContact`/`visitors`), per vehicle entry (`vehicles`), and at the
request's top level — including its existing cross-field rules: an
`individual` registration MUST NOT list additional visitors, a `group`
registration MUST list at least one, every contact/visitor entry MUST
supply at least one of email/phone, and all three consent flags MUST be
accepted. Each visitor (including the primary contact) submits their own
ID-proof file, matched by order.

Every admin-authored answer — `customFields` (a scope's list of
`{fieldId, value}` pairs), `consents` (a list of `{fieldId, accepted}`
pairs), and `groups` (a list of `{groupId, instances}` entries, each
instance itself a list of `{fieldId, value}` pairs) — is referenced by the
resolved branch's live `FormField`/`FormFieldGroup` id, never by a
key/label string, and is validated the same way invitation creation
validates it, at the same scope.

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

#### Scenario: Walk-in registration captures per-visitor and per-invitation custom field answers by field id
- **WHEN** the resolved branch's published form defines an admin-authored
  Visitor Info field and an invitation-level (Visit Details/Carried
  Items/custom-step) field, and the walk-in payload's `customFields`
  arrays supply valid `{fieldId, value}` answers for both, at their
  respective scopes
- **THEN** the registration is created with each answer persisted at its
  matching scope, the same way invitation creation persists them

#### Scenario: An answer referencing a field id the resolved branch does not define is rejected
- **WHEN** a walk-in payload's `customFields`, `consents`, or `groups`
  entry references a `fieldId`/`groupId` that does not resolve to an
  active field/group on the server-resolved branch's published form —
  whether because it doesn't exist, was deleted, or belongs to a
  different branch or tenant
- **THEN** the system rejects the request with a validation error and
  creates no registration record

### Requirement: Walk-in Registration Enforces the Server-Resolved Branch's Form-Builder Configuration
A walk-in registration's required fields, allowed custom-field/consent
field ids and their option values, and repeatable field group instance
counts SHALL be validated against the published form-builder
configuration of the branch the server itself resolves (via device
credential, or the default-tenant/default-branch fallback) — never
against a branch a client may have separately assumed or rendered. Every
such lookup resolves a submitted `fieldId`/`groupId` directly against that
branch's own field/group ids; a `fieldId`/`groupId` that is well-formed
but belongs to a different branch's form is treated identically to one
that does not exist at all — it is never resolved cross-branch. WHEN a
submitted registration is rejected because it does not match the
server-resolved branch's configuration, the system SHALL log which branch
was enforced, so a client/server branch divergence is distinguishable in
the log from any other validation failure.

#### Scenario: Submission is validated against the server-resolved branch, not a client-assumed one
- **WHEN** a walk-in registration is submitted, and the server resolves a
  branch (by device credential or default-tenant/default-branch fallback)
- **THEN** the submission's required fields, custom-field/consent field
  ids and their option values, and repeatable field group instance counts
  are validated against that resolved branch's published form-builder
  configuration, regardless of which branch's configuration the
  submitting client fetched or rendered

#### Scenario: A configuration mismatch is logged with the enforced branch
- **WHEN** a walk-in registration is rejected for a required-field,
  custom-field, group instance-count, or consent mismatch against the
  server-resolved branch's configuration
- **THEN** the rejection is logged with the resolved branch's id, so an
  operator can tell from the log whether the submitting client was
  rendering a different branch's configuration

#### Scenario: A field id belonging to a different branch is rejected as unresolvable
- **WHEN** a walk-in payload references a `fieldId`/`groupId` that exists
  on some tenant's form but not on the server-resolved branch's own
  published form
- **THEN** the system rejects the request the same way it would an
  entirely unknown id, and does not use the other branch's field
  definition to validate the submitted value
