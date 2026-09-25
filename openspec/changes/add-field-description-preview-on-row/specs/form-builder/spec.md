## ADDED Requirements

### Requirement: A Field's Description Is Visible on Its Row in the Active Form Fields List
The admin Step Editor's Active Form Fields list SHALL show a truncated
preview of a field's description on that field's own row, for any field
that has one set, so an admin can tell a description exists without
selecting the field into the Field Properties panel.

#### Scenario: A field with a description shows a preview on its row
- **WHEN** an admin views the Active Form Fields list for a step containing
  a field whose description is set
- **THEN** that field's row shows a truncated preview of the description,
  consistent with the same first-sentence truncation and "See more"/"See
  less" behavior used on the visitor-facing form

#### Scenario: A field with no description shows no preview on its row
- **WHEN** an admin views the Active Form Fields list for a step containing
  a field with no description set
- **THEN** that field's row shows no description preview and no layout
  change from a row with a description removed
