## ADDED Requirements

### Requirement: The Options-Required Exemption Is Limited to Visitor Category
A `dropdown_select`/`checkbox_list`/optioned `toggle_switch` field SHALL
require a non-empty `options` list to be created, updated, or published,
including a system-seeded field — with exactly one exception, the
`visitor_category` field, whose real options come from the separate
Visitor Categories catalog rather than this row's own `options`. A
system-seeded field other than `visitor_category` (e.g. "ID Proof Type,"
"Vehicle Type") is subject to the same non-empty-options requirement as
any admin-authored field, since its `options` are the actual source of
truth for what a submission may declare.

#### Scenario: Publishing with ID Proof Type's options emptied is rejected
- **WHEN** an admin removes every option from the "ID Proof Type" field
  (via the unlock-to-edit options editor) and attempts to publish
- **THEN** the publish is rejected, the same as it would be for any
  admin-authored dropdown field

#### Scenario: Publishing with Vehicle Type's options emptied is rejected
- **WHEN** an admin removes every option from the "Vehicle Type" field and
  attempts to publish
- **THEN** the publish is rejected, the same as for "ID Proof Type"

#### Scenario: Visitor Category remains exempt
- **WHEN** an admin views or publishes the "Visitor Category" field with an
  empty or absent `options` list on the row itself
- **THEN** the publish is not rejected for this reason — its real options
  continue to resolve from the Visitor Categories catalog at render/
  validation time, unaffected by this requirement
