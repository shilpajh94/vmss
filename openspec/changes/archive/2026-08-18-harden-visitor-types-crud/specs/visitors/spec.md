## Purpose

Baseline requirements for the `visitors` capability — configurable visitor
category CRUD (API-05) and per-category approval workflow rule CRUD
(API-06) — including the two fixes a compliance re-audit surfaced: a
soft-deleted category/rule's name/code/step must be reusable, and a
`select`-type form field must declare its selectable options.

## ADDED Requirements

### Requirement: Visitor Category CRUD With a Configurable Form Schema
The system SHALL provide full CRUD for `VisitorCategory`, tenant-wide (not
branch-scoped), each carrying a `formSchema` — an ordered list of field
definitions describing what a pre-registration/check-in form for that
category collects — validated at the API boundary before it reaches
storage.

#### Scenario: Form field names are unique within one category
- **WHEN** a `VisitorCategory` is created or updated with a `formSchema`
  containing two fields sharing the same `name`
- **THEN** the request is rejected with 422 before any database write

#### Scenario: Category CRUD requires no branch context
- **WHEN** any Visitor Category endpoint is called
- **THEN** it requires only a tenant-wide permission
  (`visitor-categories:manage`/`:view`), never an `X-Branch-ID` header

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
