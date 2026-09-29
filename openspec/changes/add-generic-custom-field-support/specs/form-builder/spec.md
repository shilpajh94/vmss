## MODIFIED Requirements

### Requirement: Fully Configurable Steps Accept Admin-Authored Fields
Every step — Visitor Info, Visit Details, Carried Items, Vehicle Info
(beyond its locked license-plate field), Consent Agreement, and any custom
step — SHALL accept an admin-authored, ordered list of fields in addition to
its own locked/toggleable seeded fields (if any). Each field declares a
field type, label, required/active state, and (per type) options and
validation rules. An admin-authored field's submitted answer SHALL be
captured on invitation/registration submission — at the per-visitor scope
for a Visitor Info field, per-vehicle scope for a Vehicle Info field, and
per-invitation scope for every other step's field, matching the scope each
step's own existing fields already use. A step accepting a field's
definition without also capturing its submitted answer does not satisfy
this requirement.

#### Scenario: Admin adds a custom carried-item checklist entry
- **WHEN** an admin adds a field of type checkbox-list labeled "Company
  Badge" to the Carried Items step and publishes
- **THEN** subsequent submissions for that branch may include "Company
  Badge" as a declared carried item

#### Scenario: Admin adds a custom consent statement
- **WHEN** an admin adds a required field to the Consent Agreement step and
  publishes
- **THEN** a submission omitting acceptance of that consent is rejected

#### Scenario: Admin adds a custom field to Visitor Info
- **WHEN** an admin adds a new field (of any supported type) to the Visitor
  Info step, alongside its existing locked/toggleable seeded fields, and
  publishes
- **THEN** the request to create the field succeeds, the field appears in
  the effective form for that branch, and a subsequent submission's answer
  for that field is captured against the specific visitor (primary contact
  or co-visitor) who answered it

#### Scenario: Admin adds a custom field to Visit Details
- **WHEN** an admin adds a new field to the Visit Details step, alongside
  its existing locked/toggleable seeded fields, and publishes
- **THEN** the request succeeds the same way it does for Visitor Info

#### Scenario: A second custom field on the same step is captured independently
- **WHEN** a step (e.g. Carried Items) already has one admin-authored field
  and an admin adds a second, distinct admin-authored field, and both are
  answered on submission
- **THEN** each field's answer is captured under its own field key — neither
  answer overwrites or is misattributed to the other

#### Scenario: A custom step's field answers are captured on submission
- **WHEN** an admin creates a custom step with one or more fields, publishes,
  and a visitor submits an answer for each
- **THEN** each answer is captured against the created invitation the same
  way an admin-authored field's answer on any other step is captured, not
  held only in the client's transient form state

## REMOVED Requirements

### Requirement: Only Fully Configurable Steps Accept New Admin-Authored Fields
**Reason**: This requirement (added by the not-yet-archived
`fix-form-builder-step-order-and-ui-gaps` change) rejected new field
creation on Visitor Info/Visit Details because those steps rendered fixed
JSX by known field keys and had no generic value-storage/rendering path for
an admin-authored field's answer. That path now exists for every step (see
the strengthened "Fully Configurable Steps Accept Admin-Authored Fields"
above), so the restriction is no longer necessary and is reversed rather
than kept as dead validation.
**Migration**: No data migration is needed — this requirement never allowed
any field to exist on Visitor Info/Visit Details, so there is nothing
previously rejected to reconcile. Any admin who previously hit the 422 on
these two steps may now create the field they originally intended.
