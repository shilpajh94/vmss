## ADDED Requirements

### Requirement: A Step's Fields May Be Organized Into Named, Repeatable Field Groups
An admin authoring a step's fields SHALL be able to define zero or more
named field groups on that step and assign each field to at most one
group; a field with no group assignment renders as a flat field directly
on the step, unchanged from today. Groups on the same step are independent
of one another and of any ungrouped fields. Groups SHALL NOT nest — a
group's own fields are always step-level fields, and a group has no
concept of containing another group.

#### Scenario: Admin creates a group and assigns fields to it
- **WHEN** an admin creates a field group on a step and assigns two of the
  step's fields to it
- **THEN** both fields are associated with that group, and the step's
  other fields are unaffected

#### Scenario: A field left ungrouped behaves as today
- **WHEN** an admin adds a field to a step without assigning it to any
  group
- **THEN** the field renders and submits exactly as a step-level field
  does today, with no group semantics applied

#### Scenario: Reassigning a field moves it out of its previous group
- **WHEN** an admin assigns a field that already belongs to one group on a
  step to a different group on the same step
- **THEN** the field belongs only to the new group afterward

#### Scenario: Groups do not nest
- **WHEN** an admin attempts to assign a field group to another field
  group as if it were a member field
- **THEN** the system offers no such action — a group's members are
  always fields, never another group

### Requirement: A Field Group May Be Marked Repeatable With a Configurable Instance Range
An admin can mark any group on a step repeatable and set an optional
minimum and maximum instance count constraining how many times the
visitor-facing form allows that group to be filled in. A non-repeatable
group is always exactly one instance. When left unset, minimum defaults to
zero (optional) and maximum defaults to unlimited. Setting a maximum lower
than the minimum SHALL be rejected.

#### Scenario: Admin marks a group repeatable with a minimum and maximum
- **WHEN** an admin marks a group repeatable with minimum 1 and maximum 5
- **THEN** the group is saved as repeatable with that instance range

#### Scenario: Admin marks a group repeatable with no explicit range
- **WHEN** an admin marks a group repeatable without setting a minimum or
  maximum
- **THEN** the group accepts any number of instances, including zero,
  matching today's unrestricted Vehicle Info behavior

#### Scenario: A maximum below the minimum is rejected
- **WHEN** an admin attempts to save a group with maximum instance count
  lower than its minimum instance count
- **THEN** the save is rejected and the group's previously saved range is
  left unchanged

### Requirement: A Field Group May Declare Conditional Visibility
The system SHALL let an admin attach a `visibilityCondition`
(`{fieldKey, operator, value}`, `operator` one of `equals`/`not_equals`)
to a field group, the same shape a field already declares, referencing
another field on the *same step*. The group — and every field inside it —
SHALL render only when that condition holds. A group's conditional-
visibility switch is independent of its repeatable switch: a group can be
conditional only, repeatable only, both, or neither.

#### Scenario: Admin makes a group conditional on another field's value
- **WHEN** an admin sets a group's `visibilityCondition` to reference an
  active field on the same step
- **THEN** the group is saved with that condition, and the visitor/staff
  form shows the group only when the watched field currently holds the
  matching value

#### Scenario: A group's condition must reference a field on the same step
- **WHEN** an admin attempts to set a group's `visibilityCondition` to a
  field that does not exist on the same step
- **THEN** the save is rejected

#### Scenario: A group's condition cannot reference one of its own member fields
- **WHEN** an admin attempts to set a group's `visibilityCondition` to a
  field that is itself assigned to that same group
- **THEN** the save is rejected as a self-reference, mirroring a field's
  own self-reference rejection

#### Scenario: A group with no condition is always visible
- **WHEN** a group has no `visibilityCondition` set
- **THEN** the group and its fields render unconditionally, matching
  today's behavior for every existing group

### Requirement: A Hidden Field Group Skips Required-Field Validation For Its Fields
When a field group's `visibilityCondition` evaluates false against a
submission's values, none of that group's fields SHALL be treated as
required for that submission, regardless of each field's own
`isRequired` flag. A field's own answer, if supplied anyway despite the
group being hidden, is still validated for type/options/length as usual —
only the missing-required check is skipped.

#### Scenario: A hidden group's required field is not required
- **WHEN** a submission's values cause a group's `visibilityCondition` to
  evaluate false, and that group contains a field marked required with no
  value supplied
- **THEN** the submission is not rejected for that field's missing value

#### Scenario: A visible group's required field is still required
- **WHEN** a submission's values cause a group's `visibilityCondition` to
  evaluate true (or the group has no condition), and that group contains
  a required field with no value supplied
- **THEN** the submission is rejected for that field's missing value,
  unchanged from today

#### Scenario: A supplied value for a hidden group's field is still validated
- **WHEN** a group is hidden per its `visibilityCondition`, but a value is
  supplied anyway for one of its fields
- **THEN** that value is still validated against the field's type/options/
  length rules, even though it wasn't required

### Requirement: A Field Group's Key Is Unique Across a Branch's Entire Active Form
A field group's key SHALL be unique across every step of a branch's
active form, mirroring the existing per-field key-uniqueness rule —
since a group's submitted instances are addressed by its key in the
invitation payload without a step qualifier, a key reused across two
groups would make a submission's group-instance array ambiguous as to
which group it answers.

#### Scenario: Creating a group with a key already used on another step is rejected
- **WHEN** an admin creates a field group with a key that already exists
  on a different step of the same branch's form
- **THEN** the request is rejected with a 409 conflict, and no group is
  created

#### Scenario: Creating a group with a key already used on the same step is rejected
- **WHEN** an admin creates a field group with a key that already exists
  on the same step
- **THEN** the request is rejected with a 409 conflict

#### Scenario: Distinct group keys across different steps are allowed
- **WHEN** an admin creates field groups with distinct keys on different
  steps of the same branch's form
- **THEN** both groups are created successfully

### Requirement: The Published Form Configuration Snapshot Includes Group Definitions
Publishing a scope's form configuration SHALL include each step's group
definitions — name, key, repeatable flag, minimum/maximum instance count,
and the ordered list of field keys within it — in the immutable snapshot
that submission validation and the visitor/staff-facing renderer read,
the same way step and field definitions already publish.

#### Scenario: Publishing after adding a repeatable group
- **WHEN** an admin adds a repeatable group to a step's draft and
  publishes
- **THEN** the published snapshot for that scope includes the group's
  definition, and subsequent submissions are validated against it

#### Scenario: An unpublished draft group change has no live effect
- **WHEN** an admin edits a draft group's minimum/maximum instance count
  without publishing
- **THEN** submission validation continues to use the last-published
  range until the next publish

### Requirement: Vehicle Info and Visitor Info Are Seeded as Locked, Repeatable Groups
Vehicle Info's vehicle fields and Visitor Info's co-visitor fields SHALL
each be seeded as a single, system (`isSystem: true`), locked, repeatable
field group on their respective steps, replacing any step-specific,
hard-coded repeat behavior with the same group mechanism available to an
admin-authored group. A locked system group SHALL NOT be deleted and
SHALL NOT be reassigned to a different step.

Vehicle Info's group behaves like any other repeatable group: it SHALL
NOT be toggled non-repeatable, and its minimum/maximum instance count
remains admin-configurable, enforced the same way a custom group's is.

Visitor Info's group's instance count is governed exclusively by the
existing registration-type rule for its *minimum* (an `individual`
invitation has no co-visitor instances; a `group` invitation has one or
more) — it SHALL NOT expose an admin-configurable minimum/maximum via the
Form Builder API, since a second, independent minimum rule on the same
group would conflict with that existing rule. Its *maximum* SHALL be
seeded from the tenant's configured group-visitor-count limit at
migration/provisioning time and enforced the same way any other group's
maximum is — this is the sole enforcement path for that limit; no
separate, non-group-based cap SHALL apply once this group's `maxInstances`
is seeded.

#### Scenario: Vehicle Info's group cannot be deleted
- **WHEN** an admin attempts to delete Vehicle Info's seeded vehicle group
- **THEN** the request is rejected and the group remains

#### Scenario: Vehicle Info's group cannot be made non-repeatable
- **WHEN** an admin attempts to toggle Vehicle Info's seeded vehicle group
  to non-repeatable
- **THEN** the request is rejected and the group remains repeatable

#### Scenario: Vehicle Info's instance range remains configurable
- **WHEN** an admin sets Vehicle Info's group maximum instance count to 5
- **THEN** the change is saved and enforced the same way a custom
  repeatable group's maximum is enforced

#### Scenario: Visitor Info's group has no configurable instance range
- **WHEN** an admin opens Visitor Info's seeded group in the Step Editor
- **THEN** no minimum/maximum instance count control is offered, and
  co-visitor cardinality continues to follow the registration-type rule

#### Scenario: Visitor Info's group enforces its seeded maximum
- **WHEN** a group registration submits more co-visitors than Visitor
  Info's group's seeded `maxInstances`
- **THEN** the submission is rejected the same way exceeding any other
  group's configured maximum is rejected
