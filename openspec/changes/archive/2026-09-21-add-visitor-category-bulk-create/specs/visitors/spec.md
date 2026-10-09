## ADDED Requirements

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
