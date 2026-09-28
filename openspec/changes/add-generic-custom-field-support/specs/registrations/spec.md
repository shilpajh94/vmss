## MODIFIED Requirements

### Requirement: Walk-in registration accepts the same visit-record contract as staff pre-registration
`POST /api/v1/registrations/walk-in` SHALL accept the identical JSON payload
shape used by invitation creation (`registrationType`, `primaryContact`,
`visitors`, `visitDetails`, `carriedItems`, `vehicles`, `consents`), plus the
same admin-authored custom-field `customFieldValues` maps invitation
creation accepts at each matching scope — per visitor entry
(`primaryContact`/`visitors`), per vehicle entry (`vehicles`), and at the
request's top level — including its existing cross-field rules: an
`individual` registration MUST NOT list additional visitors, a `group`
registration MUST list at least one, every contact/visitor entry MUST
supply at least one of email/phone, and all three consent flags MUST be
accepted. Each visitor (including the primary contact) submits their own
ID-proof file, matched by order. Each `customFieldValues` map is validated
the same way invitation creation validates it, at the same scope.

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

#### Scenario: Walk-in registration captures per-visitor and per-invitation custom field answers
- **WHEN** the resolved branch's published form defines an admin-authored
  Visitor Info field and an invitation-level (Visit Details/Carried
  Items/Consent/custom-step) field, and the walk-in payload supplies valid
  answers for both, at their respective scopes
- **THEN** the registration is created with each answer persisted at its
  matching scope, the same way invitation creation persists them
