## MODIFIED Requirements

### Requirement: Consent Is Mandatory and Recorded
An invitation SHALL be created only if the primary contact has accepted
every required consent (terms and conditions, data processing, and safety
guidelines). The system SHALL record what was consented to and when. The
consent payload (`consents`) SHALL be an array of `{fieldId, accepted}`
pairs, each `fieldId` referencing a `FormField` on the calling branch's
published Consent Agreement step — never a raw key/label string. A request
MAY omit an entry for a non-required field but SHALL NOT introduce a
`fieldId` outside that step's currently active fields, and the number of
entries accepted SHALL be capped to the size of the branch's configured
consent set.

#### Scenario: Missing consent rejected
- **WHEN** a creation request omits an `accepted: true` entry for any
  currently required Consent Agreement field
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Full consent accepted and timestamped
- **WHEN** a creation request supplies `accepted: true` for every currently
  required Consent Agreement field's `fieldId`
- **THEN** the system stores the acceptance along with the timestamp it was
  recorded

#### Scenario: Unknown consent key rejected
- **WHEN** a creation request's `consents` array includes a `fieldId` that
  is not an active field on the branch's Consent Agreement step
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Oversized consent payload rejected
- **WHEN** a creation request's `consents` array contains more entries than
  the branch's configured Consent Agreement field count
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: A consent field id belonging to a different branch is rejected
- **WHEN** a creation request's `consents` array references a `fieldId`
  that belongs to some other branch's or tenant's Consent Agreement step,
  not the resolved branch's own
- **THEN** the system rejects the request as an unknown consent field id,
  the same as a `fieldId` that does not exist at all

### Requirement: Invitation Creation Captures Admin-Defined Custom Field Answers
`POST /invitations` SHALL accept an admin-authored custom field's answer at
the same contract level its step's own existing fields already scope to,
as an array of `{fieldId, value}` pairs — never a key/label-keyed map:
- Visitor Info fields: an optional `customFields` array on each entry of
  `primaryContact` and `visitors` (one array per visitor).
- Vehicle Info fields (beyond the locked license-plate field): an optional
  `customFields` array on each entry of `vehicles` (one array per vehicle).
- Visit Details, Carried Items (beyond the `items` field's own option-set
  mechanism), and custom-step fields: an optional `customFields` array at
  the request's top level (one array per invitation). Consent Agreement is
  excluded here — every field on that step, admin-authored or seeded, is
  captured through the `consents` array instead (see "Consent Is Mandatory
  and Recorded"); a new field there needs no change from this requirement.

Each `fieldId` SHALL be resolved directly against the calling branch's
published form's live field ids — never against a key, and never against
another branch's or tenant's field sharing the same id-looking value by
coincidence. Each supplied value SHALL be validated against its resolved
field's configured type, required state, and validation rules (per
`form-builder`'s field configuration). A `fieldId` the effective form does
not define at that entity's step, a `fieldId` belonging to a different
branch, or a missing value for a currently-required custom field, SHALL be
rejected with 422. Accepted values SHALL be persisted on the matching
entity (invitation, visitor, or vehicle record), keyed by `fieldId`, and
returned in its detail response at the same scope in the same
`{fieldId, value}` shape.

#### Scenario: Per-visitor custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Visitor Info
  field and a creation request supplies a valid `{fieldId, value}` answer
  for it in a visitor's `customFields`
- **THEN** the invitation is created, that visitor's answer is persisted
  against their own visitor record keyed by that field's id, and it is
  present (as `{fieldId, value}`) in that visitor's entry in the
  invitation's detail response

#### Scenario: Two visitors answer the same custom field independently
- **WHEN** a group registration's primary contact and a co-visitor each
  supply a different answer for the same admin-authored Visitor Info
  field's `fieldId`
- **THEN** each visitor's answer is persisted and returned against their
  own record, independent of the other visitor's answer

#### Scenario: Per-vehicle custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Vehicle Info
  field and a creation request supplies a valid `{fieldId, value}` answer
  for it on one of the submitted vehicles
- **THEN** the invitation is created, that vehicle's answer is persisted
  against its own vehicle record keyed by that field's id, and it is
  present in that vehicle's entry in the invitation's detail response

#### Scenario: Invitation-level custom field answer is persisted and returned
- **WHEN** a branch's published form defines an admin-authored Visit
  Details, Carried Items, or custom-step field and a creation request
  supplies a valid `{fieldId, value}` answer for it in the request's
  top-level `customFields`
- **THEN** the invitation is created, the answer is persisted on the
  invitation itself keyed by that field's id, and it is present in the
  invitation's detail response

#### Scenario: A Consent Agreement custom field is unaffected by this requirement
- **WHEN** a branch's published form defines an admin-authored Consent
  Agreement field
- **THEN** its answer continues to be supplied and validated through the
  request's `consents` array exactly as before this change, and the
  branch's effective form does not add that field's id to the set this
  requirement validates `customFields` against

#### Scenario: Answer for an undefined field id is rejected
- **WHEN** a creation request's `customFields` (at any of the three scopes)
  includes a `fieldId` that the branch's effective form does not define
  for that entity's step
- **THEN** the request is rejected with 422 and no invitation is created

#### Scenario: A field id belonging to a different branch or tenant is rejected
- **WHEN** a creation request's `customFields` includes a `fieldId` that
  resolves to an active field, but on a different branch's or tenant's
  published form than the one the request resolved to
- **THEN** the request is rejected with 422 the same way an entirely
  unknown `fieldId` is, and no invitation is created

#### Scenario: Missing answer for a required custom field is rejected
- **WHEN** the branch's effective form marks an admin-authored field as
  required and a creation request omits its `fieldId` from the matching
  scope's `customFields`
- **THEN** the request is rejected with 422 and no invitation is created

#### Scenario: No custom fields configured, request omits all arrays
- **WHEN** a branch's published form defines no admin-authored fields beyond
  the fixed contract fields
- **THEN** a creation request omitting `customFields` at every scope is
  accepted, unaffected by this requirement

### Requirement: An Admin-Defined Repeatable Group's Answers Are Accepted as an Array of Per-Instance Values
For a repeatable field group an admin has defined on any step other than
the seeded Vehicle Info/Visitor Info groups, the system SHALL accept that
group's answers in the invitation-creation (and walk-in registration)
request as one entry of the top-level `groups` array —
`{groupId, instances}`, where `groupId` references the group's live id and
`instances` is an ordered array of per-instance `customFields`-shaped
(`{fieldId, value}` pair list) value sets. The system SHALL validate each
instance's values against the group's field definitions the same way a
flat step's answers are validated today, resolving both `groupId` and
every instance's `fieldId`s directly against the calling branch's live
group/field ids, and SHALL reject a submission whose instance count falls
outside the group's currently published minimum/maximum, or whose
`groupId` does not resolve to an active, admin-defined group on that
branch. A rejected submission SHALL persist no instance of that group,
consistent with the existing "validate everything before persisting
anything" pattern used for ID-proof files.

#### Scenario: Submission within the group's configured range is accepted
- **WHEN** a creation request's `groups` array supplies a number of
  instances for a custom repeatable group (`{groupId, instances}`) within
  its published minimum and maximum
- **THEN** the request is accepted, each instance's values are persisted,
  and they are retrievable from the invitation's detail response in
  submission order, keyed by `groupId` and each instance's `fieldId`s

#### Scenario: Instance count below the configured minimum is rejected
- **WHEN** a creation request submits fewer instances of a repeatable
  group than its published minimum
- **THEN** the system rejects the request with a validation error and
  creates no invitation

#### Scenario: Instance count above the configured maximum is rejected
- **WHEN** a creation request submits more instances of a repeatable group
  than its published maximum
- **THEN** the system rejects the request with a validation error and
  creates no invitation

#### Scenario: One invalid instance rejects the whole submission
- **WHEN** a creation request submits several instances of a repeatable
  group and one instance's field value fails validation
- **THEN** the system rejects the entire request and persists no instance
  of that group

#### Scenario: An unresolvable group id is rejected
- **WHEN** a creation request's `groups` array includes a `groupId` that
  does not resolve to an active, admin-defined field group on the
  server-resolved branch's published form — whether unknown, deleted, or
  belonging to a different branch or tenant
- **THEN** the system rejects the request with a validation error and
  creates no invitation
