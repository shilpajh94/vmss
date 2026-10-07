## ADDED Requirements

### Requirement: Wizard Fields Stack in One Column on Narrow Screens
Below the `sm` breakpoint (640px), every field of a wizard step SHALL
occupy the full width of the step's card, one field per row, whether or
not the step has admin-authored custom fields. No field SHALL be laid out
beside another at those widths. No label or input SHALL be narrowed below
the card's content width. From `sm` upward, the step's two-column layout
SHALL be unchanged, and admin-authored custom fields SHALL span the full
row.

#### Scenario: Visitor Info on a phone with a custom field
- **WHEN** the Visitor Info step renders at 375px wide and the published
  form includes an admin-authored field such as the "Terms & Conditions"
  consent checkbox
- **THEN** Full Name, Email Address, Phone Number, Visitor Category,
  Preferred Contact Method, ID Proof Type, Upload ID, Profile Image, and
  the custom field each render full-width, one per row, with their labels
  on a single line where they fit and their inputs showing the full
  placeholder

#### Scenario: Two columns from the sm breakpoint
- **WHEN** the same step renders at 768px wide
- **THEN** the system fields render two per row as before, and the custom
  fields section spans the whole row beneath them
