## Purpose

Lets an admin configure the steps and fields of the visitor registration
form per branch (falling back to a tenant-wide default), and exposes the
currently published configuration for invitation/registration submission to
validate against and for the frontend to render.

## ADDED Requirements

### Requirement: Six Canonical Steps Exist By Default
Every tenant SHALL start with six canonical steps in a fixed default order:
Visitor Info, Visit Details, Carried Items, Vehicle Info, Consent Agreement,
Review & Confirm. Visitor Info, Visit Details, and Review & Confirm SHALL be
**locked** steps that can never be deactivated or removed. Carried Items,
Vehicle Info, and Consent Agreement SHALL be **toggleable** steps that an
admin may deactivate or remove. An admin MAY also create additional custom
steps, which are toggleable/removable the same as the non-locked defaults.

#### Scenario: Locked step cannot be deactivated
- **WHEN** an admin attempts to deactivate or delete the Visitor Info, Visit
  Details, or Review & Confirm step
- **THEN** the request is rejected with 422 and the step remains active

#### Scenario: Toggleable step can be deactivated
- **WHEN** an admin deactivates the Carried Items step
- **THEN** the step is marked inactive in the draft configuration and, once
  published, is omitted from the effective form and from submission
  validation for that branch

#### Scenario: A new tenant is provisioned with the six default steps active
- **WHEN** a tenant is provisioned
- **THEN** its tenant-default form configuration contains all six canonical
  steps, active, in the default order, seeded with the field set described
  in "System Fields Are Seeded With a Locked or Toggleable Tier"

### Requirement: System Fields Are Seeded With a Locked or Toggleable Tier
Each of Visitor Info and Visit Details SHALL be seeded with its existing
fixed fields, each tagged as either **locked** (always active and required,
only label/placeholder/help-text editable) or **toggleable** (admin may
activate/deactivate and, when active, toggle required):
- Visitor Info locked: full name, email-or-phone contact, visitor category.
- Visitor Info toggleable: registration type (option set: `individual`,
  `group`), preferred contact method (option set: `email`, `sms`), ID-proof
  type, ID-proof upload, profile photo.
- Visit Details locked: purpose of visit, host, preferred visit date/time,
  department.
- Visit Details toggleable: expected duration, additional notes.
- Vehicle Info locked (only meaningful while the step is active): license
  plate.

A locked field's `required`/`active` state SHALL NOT be settable through the
field-update endpoint; requests attempting to change either are rejected.

#### Scenario: Locked field's required flag cannot be changed
- **WHEN** an admin submits a field update for a locked field (e.g. full
  name) with `required: false` or `active: false`
- **THEN** the request is rejected with 422 and the field's required/active
  state is unchanged

#### Scenario: Toggleable field can be deactivated
- **WHEN** an admin deactivates the "Additional Notes" field on Visit
  Details
- **THEN** the field is marked inactive in the draft, and once published,
  submissions are no longer required (or permitted, per the field's own
  contract) to supply it

#### Scenario: Option-set field restricts submission to selected options
- **WHEN** an admin configures "Preferred Contact Method" with only `email`
  enabled and publishes
- **THEN** a subsequent submission with `preferredContactMethod: "sms"` for
  that branch is rejected as an invalid option

### Requirement: Fully Configurable Steps Accept Admin-Authored Fields
Carried Items, Vehicle Info (beyond its locked license-plate field), Consent
Agreement, and any custom step SHALL accept an admin-authored, ordered list
of fields with no fixed field set of their own. Each field declares a field
type, label, required/active state, and (per type) options and validation
rules.

#### Scenario: Admin adds a custom carried-item checklist entry
- **WHEN** an admin adds a field of type checkbox-list labeled "Company
  Badge" to the Carried Items step and publishes
- **THEN** subsequent submissions for that branch may include "Company
  Badge" as a declared carried item

#### Scenario: Admin adds a custom consent statement
- **WHEN** an admin adds a required field to the Consent Agreement step and
  publishes
- **THEN** a submission omitting acceptance of that consent is rejected

### Requirement: Field Types Are Constrained To a Supported Set
A field's type SHALL be one of: text, email, phone, number, dropdown-select,
date-picker, time-picker, toggle-switch, checkbox-list, file-upload,
textarea, dynamic-table, rich-text-block, signature-pad. Fields whose type
requires a set of selectable options (dropdown-select, checkbox-list,
toggle-switch when used as an option set) SHALL declare a non-empty
`options` list.

#### Scenario: Unsupported field type rejected
- **WHEN** a field is created or updated with a `fieldType` outside the
  supported set
- **THEN** the request is rejected with 422 before any draft write

#### Scenario: Option-bearing field with no options rejected
- **WHEN** a `dropdown-select` or `checkbox-list` field is created or
  updated with an empty or absent `options` list
- **THEN** the request is rejected with 422 before any draft write

### Requirement: A Field May Declare Conditional Visibility
A field MAY declare a visibility condition referencing another field in the
same step by key and a comparison value. When present, the referenced field
SHALL exist in the same step and SHALL NOT itself declare a condition that
transitively (directly or indirectly) depends on this field.

#### Scenario: Conditionally visible field's condition is validated against a real field
- **WHEN** a field's visibility condition references a field key that does
  not exist in the same step
- **THEN** the request is rejected with 422

#### Scenario: Circular condition rejected
- **WHEN** field A's visibility condition depends on field B, and field B's
  visibility condition is set to depend on field A
- **THEN** the request that creates the cycle is rejected with 422

### Requirement: A Field Declares Validation Rules and Display Width
A field MAY declare type-appropriate validation rules (e.g. min/max length
for text, min/max for number) and SHALL declare a display width of `half` or
`full`, defaulting to `full`.

#### Scenario: Min length greater than max length rejected
- **WHEN** a text field's validation rules set `minLength` greater than
  `maxLength`
- **THEN** the request is rejected with 422

#### Scenario: A submission violating a field's validation rule is rejected
- **WHEN** a submitted value for a field is shorter than its configured
  `minLength`
- **THEN** the submission is rejected with a validation error identifying
  the offending field

### Requirement: Fields and Steps Are Explicitly Ordered
Each step SHALL have an explicit order among its tenant/branch siblings, and
each field an explicit order among its step siblings. Reordering SHALL
persist the new order without requiring a delete/recreate of any field or
step.

#### Scenario: Reordering fields persists across reads
- **WHEN** an admin reorders the fields of a step and saves
- **THEN** a subsequent read of that step's fields returns them in the new
  order

### Requirement: Configuration Is Branch-Scoped With a Tenant-Level Default
Form configuration SHALL be resolvable per branch. A branch with no
configuration of its own SHALL resolve to the tenant's default
configuration. An admin customizing a branch for the first time SHALL start
from a copy of the tenant's current default (or another branch's, per admin
choice) rather than an empty form.

#### Scenario: Branch without its own configuration inherits the tenant default
- **WHEN** invitation submission or the admin UI requests the effective form
  for a branch that has never been individually configured
- **THEN** the tenant's default published configuration is returned

#### Scenario: Branch-specific configuration overrides the tenant default
- **WHEN** a branch has its own published configuration
- **THEN** submissions and reads for that branch use the branch's
  configuration, not the tenant default, regardless of later changes to the
  tenant default

### Requirement: Draft Edits Do Not Affect Live Submission Until Published
All step/field create/update/delete/reorder operations SHALL apply to a
draft configuration. Invitation/registration submission and the frontend's
live-rendered form SHALL validate against the most recently **published**
configuration only, never an unpublished draft.

#### Scenario: Unpublished draft edit has no effect on submission
- **WHEN** an admin deactivates a field in the draft but does not publish
- **THEN** submissions continue to be validated against the previously
  published configuration, unaffected by the draft edit

#### Scenario: Publish makes the draft the new live configuration
- **WHEN** an admin publishes a draft
- **THEN** subsequent submissions and effective-form reads for that scope
  (branch or tenant default) reflect the newly published configuration, and
  the previously published configuration is no longer used for new
  submissions

### Requirement: Publishing Requires the Configuration To Be Internally Valid
A publish request SHALL be rejected if the draft fails validation as a whole
(e.g. a dangling conditional-visibility reference, an option-bearing field
with no options, a locked field improperly marked inactive) — the same
constraints enforced on individual create/update calls, re-checked at the
configuration level in case of a partial or concurrent edit.

#### Scenario: Publish rejected on an invalid draft
- **WHEN** a draft contains a field whose conditional-visibility reference
  no longer resolves (its target field was since deleted)
- **THEN** the publish request is rejected with 422 and the previously
  published configuration remains live

### Requirement: Form Builder Access Is Permission-Gated
Reading a branch's or the tenant default's draft/published configuration
through the admin API SHALL require `form-builder:view`; creating, updating,
reordering, deleting, or publishing SHALL require `form-builder:manage`.
Resolving the effective form for submission validation is an internal read
that does not itself require either permission (it is invoked by the
invitation/registration flow, not directly by an admin caller).

#### Scenario: Caller without form-builder:manage cannot publish
- **WHEN** a caller holding only `form-builder:view` attempts to publish a
  draft
- **THEN** the request is rejected with 403

#### Scenario: Caller without form-builder:view cannot read the draft
- **WHEN** a caller holding neither `form-builder:view` nor
  `form-builder:manage` requests a step's fields
- **THEN** the request is rejected with 403

### Requirement: Publishing a Configuration Is Audited
Publishing a draft configuration (branch-specific or tenant default) SHALL
be recorded in the tenant's audit trail, consistent with
`security-architecture.md` §5, identifying the acting user, the scope
(branch id or tenant default), and the resulting version identifier.

#### Scenario: Publish action is audited
- **WHEN** an admin publishes a draft
- **THEN** an audit log entry is written recording the actor, the scope
  published, and the new version identifier
