## MODIFIED Requirements

### Requirement: Visitor Category CRUD With a Configurable Form Schema
The system SHALL provide full CRUD for `VisitorCategory`, tenant-wide (not
branch-scoped). Each category SHALL carry a display badge color, an NDA
requirement, an escort requirement, and a maximum visit duration. A
category no longer carries its own `formSchema`; category-specific
registration fields are instead authored in the `form-builder` capability
as Visitor Info fields with a conditional-visibility rule keyed on the
selected visitor category (see `form-builder`'s "A Field May Declare
Conditional Visibility").

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

#### Scenario: Form field names are unique within one category
- **WHEN** a `VisitorCategory` create or update request includes a
  `formSchema` field
- **THEN** the field is ignored (not persisted, and no per-field
  name-uniqueness validation is performed on it), since a category no
  longer carries its own form schema — category-specific fields are now
  authored through `form-builder`

## REMOVED Requirements

### Requirement: A Select-Type Form Field Declares Its Options
**Reason**: `VisitorCategory.form_schema` and its `FormFieldDefinition`
field list are removed — never wired into invitation creation, and
superseded by the `form-builder` capability's own step/field model, which
enforces the equivalent constraint ("Field Types Are Constrained To a
Supported Set": an option-bearing field must declare a non-empty `options`
list) for every field type, not just category-specific ones.

**Migration**: Any category-specific field previously modeled in a
category's `form_schema` should be recreated as a Visitor Info field in
`form-builder`, with a conditional-visibility rule scoping it to that
category. No stored `form_schema` data is migrated automatically — it was
not yet consumed by any code path (no `VisitorCategory` row's `form_schema`
has ever affected invitation creation), so there is no submission history
depending on it.
