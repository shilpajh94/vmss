## MODIFIED Requirements

### Requirement: Carried Items and Vehicles Are Optional Structured Declarations
The system SHALL accept zero or more carried-item declarations (each an
item category plus an optional free-text description). The system SHALL
accept vehicle declarations (each a vehicle type, license plate,
make/model, and color) up to the branch's currently published minimum and
maximum instance count for the Vehicle Info field group, defaulting to no
minimum and no maximum when the admin has not configured either — matching
today's unrestricted behavior. The system SHALL accept a request that
declares neither carried items nor vehicles whenever the Vehicle Info
group's minimum is zero.

#### Scenario: Request with no items or vehicles accepted
- **WHEN** a creation request omits carried items and vehicles entirely,
  and the branch's Vehicle Info group has a minimum of zero
- **THEN** the system accepts the request as long as all other
  requirements are met

#### Scenario: Multiple vehicles recorded
- **WHEN** a creation request lists more than one vehicle, within the
  branch's configured maximum
- **THEN** the system stores each vehicle as a separate record linked to
  the invitation

#### Scenario: Vehicle count below the configured minimum is rejected
- **WHEN** a branch's Vehicle Info group has a minimum instance count of 1
  and a creation request declares zero vehicles
- **THEN** the system rejects the request with a validation error

#### Scenario: Vehicle count above the configured maximum is rejected
- **WHEN** a branch's Vehicle Info group has a maximum instance count of 3
  and a creation request declares four vehicles
- **THEN** the system rejects the request with a validation error

## ADDED Requirements

### Requirement: An Admin-Defined Repeatable Group's Answers Are Accepted as an Array of Per-Instance Values
For a repeatable field group an admin has defined on any step other than
the seeded Vehicle Info/Visitor Info groups, the system SHALL accept that
group's answers as an ordered array of per-instance value maps in the
invitation-creation (and walk-in registration) request, validate each
instance's values against the group's field definitions the same way a
flat step's answers are validated today, and reject a submission whose
instance count falls outside the group's currently published
minimum/maximum. A rejected submission SHALL persist no instance of that
group, consistent with the existing "validate everything before
persisting anything" pattern used for ID-proof files.

#### Scenario: Submission within the group's configured range is accepted
- **WHEN** a creation request submits a number of instances for a custom
  repeatable group within its published minimum and maximum
- **THEN** the request is accepted, each instance's values are persisted,
  and they are retrievable from the invitation's detail response in
  submission order

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

### Requirement: A Hidden Custom Field Group's Fields Are Not Required At Submission
When a custom field group's `visibilityCondition` evaluates false against
a creation request's submitted values, the system SHALL NOT reject that
request for a missing value on any of that group's required fields, and
SHALL NOT reject it for submitting fewer instances of that group than its
configured minimum instance count — a visitor who was never shown a
hidden group cannot be expected to have filled it in. The group's
configured maximum instance count still applies if instances are
submitted anyway. A value supplied anyway for a field in a hidden group
is still validated against that field's type/options/length rules.

#### Scenario: Submission omits a hidden group's required field
- **WHEN** a creation request's values cause a custom field group's
  `visibilityCondition` to evaluate false, and that group has a required
  field with no submitted value
- **THEN** the system accepts the request as long as every other
  requirement is met

#### Scenario: Submission omits a visible group's required field
- **WHEN** a creation request's values cause a custom field group's
  `visibilityCondition` to evaluate true (or the group has no condition),
  and that group has a required field with no submitted value
- **THEN** the system rejects the request, unchanged from today's
  required-field behavior

### Requirement: A Group Registration's Visitor Count Is Capped By the Visitor Info Group's Configured Maximum
The system SHALL reject a group-registration creation request whose
visitor list (excluding the primary contact) exceeds the calling branch's
Visitor Info field group's currently published maximum instance count.
This formalizes, as a spec requirement enforced through the same
group-instance-count mechanism every other group uses, a cap that
previously existed only as an undocumented server-side constant with no
per-branch configurability.

#### Scenario: Visitor count within the configured maximum is accepted
- **WHEN** a group registration's visitor list is within the branch's
  Visitor Info group's currently published maximum
- **THEN** the system accepts the request as long as every other
  requirement is met

#### Scenario: Visitor count above the configured maximum is rejected
- **WHEN** a group registration's visitor list exceeds the branch's
  Visitor Info group's currently published maximum
- **THEN** the system rejects the request with a validation error and
  creates no invitation
