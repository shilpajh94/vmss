## ADDED Requirements

### Requirement: Workspace selector lists "Tenant Default" exactly once

The Form Builder workspace selector SHALL list the "Tenant Default" choice
exactly once, followed by exactly one entry per branch, and selecting
"Tenant Default" SHALL load the tenant-default (non-branch) registration steps.

#### Scenario: Opening the workspace dropdown
- **WHEN** a tenant admin opens the workspace dropdown on `/admin/form-builder`
  for a tenant with branches "Main Branch" and "QA Form Builder Branch"
- **THEN** the dropdown lists exactly three entries, in order: "Tenant Default",
  "Main Branch", "QA Form Builder Branch"

#### Scenario: Initial selection
- **WHEN** the Form Builder page first loads
- **THEN** the selector shows "Tenant Default" as the current selection and the
  tenant-default steps are displayed

#### Scenario: Switching back to Tenant Default
- **WHEN** the admin selects a branch and then selects "Tenant Default"
- **THEN** the tenant-default steps are loaded and "Tenant Default" is shown as
  the current selection

### Requirement: Conditional-visibility selectors list "Always shown" exactly once

The "Show this field when:" selector in the field properties panel and the
"Show this group when:" selector on a group card SHALL each list the
"Always shown" choice exactly once, followed by the pickable fields. Selecting
"Always shown" SHALL clear the visibility condition: the operator and value
inputs are hidden and the saved condition is empty.

#### Scenario: Opening a conditional-visibility dropdown
- **WHEN** the admin opens the "Show this field when:" or "Show this group when:"
  dropdown
- **THEN** "Always shown" appears exactly once, as the first entry

#### Scenario: Clearing an existing condition
- **WHEN** a field or group has a visibility condition and the admin selects
  "Always shown"
- **THEN** the operator and value inputs are hidden
- **AND** saving persists no visibility condition for that field or group

#### Scenario: Element with no condition
- **WHEN** the admin opens a field or group that has no visibility condition
- **THEN** the selector shows "Always shown" and no operator/value inputs are
  displayed
