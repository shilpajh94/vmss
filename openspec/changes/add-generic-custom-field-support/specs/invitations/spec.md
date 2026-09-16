## ADDED Requirements

### Requirement: Invitation Creation Captures Admin-Defined Custom Field Answers
`POST /invitations` SHALL accept an admin-authored custom field's answer at
the same contract level its step's own existing fields already scope to:
- Visitor Info fields: an optional `customFieldValues` map on each entry of
  `primaryContact` and `visitors` (one map per visitor).
- Vehicle Info fields (beyond the locked license-plate field): an optional
  `customFieldValues` map on each entry of `vehicles` (one map per vehicle).
- Visit Details, Carried Items (beyond the `items` field's own option-set
  mechanism), and custom-step fields: an optional `customFieldValues` map
  at the request's top level (one map per invitation). Consent Agreement is
  excluded here — every field on that step, admin-authored or seeded, has
  always been captured through the existing `consents` map instead (see
  "Consent Is Mandatory and Recorded"); a new field there needs no change
  from this requirement.

Each supplied value SHALL be validated against its field's configured type,
required state, and validation rules (per `form-builder`'s field
configuration), resolved from the calling branch's published form. A value
supplied for a key the effective form does not define at that entity's
step, or a missing value for a currently-required custom field, SHALL be
rejected with 422. Accepted values SHALL be persisted on the matching
entity (invitation, visitor, or vehicle record) and returned in its detail
response at the same scope.

#### Scenario: Per-visitor custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Visitor Info
  field and a creation request supplies a valid answer for it in a
  visitor's `customFieldValues`
- **THEN** the invitation is created, that visitor's answer is persisted
  against their own visitor record, and it is present in that visitor's
  entry in the invitation's detail response

#### Scenario: Two visitors answer the same custom field independently
- **WHEN** a group registration's primary contact and a co-visitor each
  supply a different answer for the same admin-authored Visitor Info field
- **THEN** each visitor's answer is persisted and returned against their
  own record, independent of the other visitor's answer

#### Scenario: Per-vehicle custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Vehicle Info
  field and a creation request supplies a valid answer for it on one of the
  submitted vehicles
- **THEN** the invitation is created, that vehicle's answer is persisted
  against its own vehicle record, and it is present in that vehicle's entry
  in the invitation's detail response

#### Scenario: Invitation-level custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Visit
  Details, Carried Items, or custom-step field and a creation request
  supplies a valid answer for it in the request's top-level
  `customFieldValues`
- **THEN** the invitation is created, the answer is persisted on the
  invitation itself, and it is present in the invitation's detail response

#### Scenario: A Consent Agreement custom field is unaffected by this requirement
- **WHEN** a branch's published form defines an admin-authored Consent
  Agreement field
- **THEN** its answer continues to be supplied and validated through the
  request's `consents` map exactly as before this change, and the branch's
  effective form does not add that field's key to the set this requirement
  validates `customFieldValues` against

#### Scenario: Answer for an undefined field key is rejected
- **WHEN** a creation request's `customFieldValues` (at any of the three
  scopes) includes a key that the branch's effective form does not define
  for that entity's step
- **THEN** the request is rejected with 422 and no invitation is created

#### Scenario: Missing answer for a required custom field is rejected
- **WHEN** the branch's effective form marks an admin-authored field as
  required and a creation request omits its key from the matching scope's
  `customFieldValues`
- **THEN** the request is rejected with 422 and no invitation is created

#### Scenario: No custom fields configured, request omits all maps
- **WHEN** a branch's published form defines no admin-authored fields beyond
  the fixed contract fields
- **THEN** a creation request omitting `customFieldValues` at every scope is
  accepted, unaffected by this requirement
