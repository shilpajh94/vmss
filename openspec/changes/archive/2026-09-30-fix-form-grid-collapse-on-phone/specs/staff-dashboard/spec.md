## ADDED Requirements

### Requirement: Visitor Info Modal Details Stack in One Column on Narrow Screens
Below the `sm` breakpoint, each detail section of the Visitor Info modal
SHALL list its label/value pairs one per row, at the full width of the
section. That covers visit details, contact details, vehicles and
additional notes. A full-width entry (such as notes) SHALL NOT cause the
other entries to pack side by side. From `sm` upward, the two-column
layout SHALL be unchanged.

#### Scenario: Visitor Info modal on a phone
- **WHEN** a staff user opens a visit's Visitor Info modal at 375px wide
- **THEN** each detail label and its value render at the section's full
  width, one entry per row, and the notes entry spans the section
