## Purpose

The form-builder capability lets a tenant admin configure, per branch,
which registration steps and custom fields a visitor registration or
invitation form presents, and enforces that configuration's constraints
when a registration/invitation is submitted.

## ADDED Requirements

### Requirement: A Custom Field's Key Is Unique Across a Branch's Entire Active Form
A custom field's key SHALL be unique across every step of a branch's
active form, not only within the step it is being added to — since
submission-time validation resolves a submitted value's field definition
by key across all of a branch's active steps at once, a key reused across
two steps would otherwise have one step's field definition silently
shadow the other's when validating a submitted value.

#### Scenario: Creating a field with a key already used on another step is rejected
- **WHEN** an admin creates a custom field with a key that already exists
  on a different active step of the same branch's form
- **THEN** the request is rejected with a 409 conflict, and no field is
  created

#### Scenario: Creating a field with a key already used on the same step is still rejected
- **WHEN** an admin creates a custom field with a key that already exists
  on the same step
- **THEN** the request is rejected with a 409 conflict, matching today's
  existing per-step uniqueness check

#### Scenario: Distinct keys across different steps are allowed
- **WHEN** an admin creates custom fields with distinct keys on different
  steps of the same branch's form
- **THEN** both fields are created successfully
