# visitors Specification

## Purpose

Baseline requirements for the `visitors` capability — configurable visitor
category CRUD (API-05) and per-category approval workflow rule CRUD
(API-06) — including the two fixes a compliance re-audit surfaced: a
soft-deleted category/rule's name/code/step must be reusable, and a
`select`-type form field must declare its selectable options.

## Requirements

### Requirement: Visitor Category CRUD With a Configurable Form Schema
The system SHALL provide full CRUD for `VisitorCategory`, tenant-wide (not
branch-scoped), each carrying a `formSchema` — an ordered list of field
definitions describing what a pre-registration/check-in form for that
category collects — validated at the API boundary before it reaches
storage. Each category SHALL additionally carry a display badge color, an
NDA requirement, an escort requirement, and a maximum visit duration.

#### Scenario: Form field names are unique within one category
- **WHEN** a `VisitorCategory` is created or updated with a `formSchema`
  containing two fields sharing the same `name`
- **THEN** the request is rejected with 422 before any database write

#### Scenario: Category CRUD requires no branch context
- **WHEN** any Visitor Category endpoint is called
- **THEN** it requires only a tenant-wide permission
  (`visitor-categories:manage`/`:view`), never an `X-Branch-ID` header

#### Scenario: A category declares its badge color, NDA, and escort policy
- **WHEN** a caller with `visitor-categories:manage` creates or updates a
  `VisitorCategory` with `badgeColor`, `ndaRequirement` (one of `digital`,
  `signed_pdf`, `optional`, `none`), `escortRequirement` (one of
  `self_escort`, `access_logs_only`, `always_required`,
  `gate_check_in_only`), and `maxDurationMinutes`
- **THEN** the values are persisted and returned on subsequent reads of that
  category

#### Scenario: An invalid NDA or escort requirement value is rejected
- **WHEN** a `VisitorCategory` create or update request sets
  `ndaRequirement` or `escortRequirement` to a value outside its defined set
- **THEN** the request is rejected with 422 before any database write

### Requirement: Approval Workflow Rule CRUD Per Category
The system SHALL provide full CRUD for `ApprovalWorkflowRule`, each rule
belonging to exactly one `VisitorCategory` and referencing an approver
`Role`, ordered by `stepOrder` starting at 1. Whether a category requires
approval SHALL be derived from whether it has any active rules, not stored
as a separate flag.

#### Scenario: Creating a rule validates its category and approver role exist
- **WHEN** a rule is created referencing a `visitorCategoryId` or
  `approverRoleId` that does not exist in the tenant's schema
- **THEN** the request is rejected with 404 and no rule is created

#### Scenario: A category with zero rules is walk-in/pre-approved
- **WHEN** a `VisitorCategory` has no `ApprovalWorkflowRule` rows
- **THEN** nothing in this capability's data model marks it as requiring
  approval — that determination is made by reading rule presence, not a
  stored boolean

### Requirement: A Soft-Deleted Category or Rule's Unique Value Is Reusable
`VisitorCategory.name`, `VisitorCategory.code`, and
`ApprovalWorkflowRule(visitorCategoryId, stepOrder)` SHALL enforce
uniqueness only among rows that are not soft-deleted, so a new row may reuse
the name/code/step of a previously soft-deleted row of the same type.

#### Scenario: Recreating a category with a soft-deleted row's code succeeds
- **WHEN** a `VisitorCategory` is soft-deleted, and a new category is then
  created with the same `code` (or `name`)
- **THEN** the creation succeeds with 201, rather than failing on a
  database-level uniqueness violation

#### Scenario: Recreating a rule at a soft-deleted row's step order succeeds
- **WHEN** an `ApprovalWorkflowRule` at a given `stepOrder` for a category is
  soft-deleted, and a new rule for the same category is then created at that
  same `stepOrder`
- **THEN** the creation succeeds with 201

#### Scenario: A genuine duplicate among active rows is still rejected
- **WHEN** a create or update request would result in two *non-deleted*
  categories sharing a name/code, or two non-deleted rules for the same
  category sharing a step order
- **THEN** the request is rejected with 409, whether caught by the
  application-level pre-check or, in a concurrent-request race, by the
  database constraint itself

### Requirement: A Select-Type Form Field Declares Its Options
A `FormFieldDefinition` with `fieldType: select` SHALL declare a non-empty
list of `options`.

#### Scenario: Select field with no options is rejected
- **WHEN** a `VisitorCategory` create or update request includes a
  `formSchema` field with `fieldType: select` and `options` absent, null, or
  an empty list
- **THEN** the request is rejected with 422 before any database write

### Requirement: Visitor Categories Can Be Bulk-Created From a List of Names
The system SHALL let a caller with `visitor-categories:manage` create
multiple `VisitorCategory` rows in one request from a list of names alone.
Each name's `code` SHALL be derived from that name the same way a Form
Builder custom field's `key` is derived from its label. A name (or its
derived code) that collides with an existing, non-deleted category SHALL be
skipped rather than causing the whole batch to fail, and the response SHALL
report, per submitted name, whether it was created or skipped and why.

#### Scenario: All submitted names are new
- **WHEN** a caller with `visitor-categories:manage` submits a bulk-create
  request with names that don't match any existing category's name or
  derived code
- **THEN** a `VisitorCategory` is created for each name, and the response
  lists all of them as created

#### Scenario: Some submitted names already exist
- **WHEN** a bulk-create request includes a mix of names that are new and
  names that match an existing category's name or derived code
- **THEN** the new names are created, the colliding names are skipped, and
  the response reports each submitted name's outcome individually —
  created, or skipped with the reason

#### Scenario: The submitted list contains a duplicate name
- **WHEN** a bulk-create request's own list contains the same name more
  than once
- **THEN** one `VisitorCategory` is created for that name and every later
  occurrence in the same request is reported as skipped

#### Scenario: An empty or all-blank submission is rejected
- **WHEN** a bulk-create request's name list is empty, or contains only
  blank/whitespace-only entries
- **THEN** the request is rejected with 422 before any database write

#### Scenario: Bulk-create requires the same permission as single create
- **WHEN** any caller invokes the bulk-create endpoint
- **THEN** it requires `visitor-categories:manage`, the same permission
  `POST /visitor-categories` already requires, and a caller without it
  receives a 403
