## MODIFIED Requirements

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
