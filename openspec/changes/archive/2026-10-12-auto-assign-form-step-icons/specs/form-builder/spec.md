## ADDED Requirements

### Requirement: Registration Step Icons Come From a Fixed Vocabulary
The system SHALL define a single, documented vocabulary of registration-step
icon slugs that every client renders from. The vocabulary SHALL include at
least: `user`, `calendar`, `briefcase`, `package`, `car`, `shield-check`,
`check-circle`, `file-text`, `file-signature`, `id-card`, `camera`,
`heart-pulse`, `laptop`, `phone`, `building`, `users`, `clock`, `map-pin`,
`alert-triangle`, and `clipboard-list` (the neutral default). Every seeded
default step's icon SHALL be a member of this vocabulary.

#### Scenario: Seeded default steps use vocabulary icons
- **WHEN** a branch's form is seeded with the default registration steps
- **THEN** every seeded step's `icon` is a slug from the vocabulary, with
  "Vehicle Info" seeded as `car` and "Carried Items" as `briefcase`

### Requirement: A Step Created Without an Icon Is Assigned One Matching Its Name
When a registration step is created and the request omits `icon` (or sends
`null` or an empty string), the system SHALL assign an icon slug from the
vocabulary by matching keywords in the step's name, case-insensitively and
on whole words or word prefixes. When no keyword matches, the system SHALL
assign the neutral default `clipboard-list`. A created step SHALL never be
persisted with a null icon.

#### Scenario: Vehicle step gets a car icon
- **WHEN** an admin creates a step named "Vehicle Info" without an icon
- **THEN** the created step's `icon` is `car`

#### Scenario: Agreement step gets a signature icon
- **WHEN** an admin creates a step named "NDA Signing" without an icon
- **THEN** the created step's `icon` is `file-signature`

#### Scenario: Health step gets a health icon
- **WHEN** an admin creates a step named "Health Declaration" without an icon
- **THEN** the created step's `icon` is `heart-pulse`

#### Scenario: Matching ignores case and plural forms
- **WHEN** an admin creates a step named "VEHICLES" without an icon
- **THEN** the created step's `icon` is `car`

#### Scenario: Unmatched name gets the neutral default
- **WHEN** an admin creates a step named "Miscellaneous" without an icon
- **THEN** the created step's `icon` is `clipboard-list`

#### Scenario: An explicit icon is honoured as sent
- **WHEN** an admin creates a step named "Vehicle Info" with `icon` set to
  `package`
- **THEN** the created step's `icon` is `package`, not the inferred `car`

### Requirement: Renaming a Step Re-Derives an Icon That Was Never Chosen Explicitly
When a step's name is updated and the update does not set `icon`, the system
SHALL re-derive the icon from the new name if, and only if, the step's
current icon equals the icon the previous name would have been assigned (or
is null). An icon that differs from the previous name's derived icon SHALL be
treated as explicitly chosen and left unchanged.

#### Scenario: Auto-assigned icon follows a rename
- **WHEN** a step named "Miscellaneous" with icon `clipboard-list` is renamed
  to "Laptop Declaration" without sending an icon
- **THEN** the step's `icon` becomes `laptop`

#### Scenario: Explicitly chosen icon survives a rename
- **WHEN** a step named "Vehicle Info" with icon `package` is renamed to
  "Parking Details" without sending an icon
- **THEN** the step's `icon` remains `package`

#### Scenario: Rename with an explicit icon uses the sent icon
- **WHEN** a step is renamed and the same update sets `icon` to `camera`
- **THEN** the step's `icon` is `camera`

### Requirement: A Stored Step Without an Icon Is Served With a Derived Icon
When a registration step stored with a null icon is returned by any
form-builder step endpoint or by the effective-form payload, the system SHALL
return the icon derived from the step's name in place of null, without
requiring a data migration.

#### Scenario: Legacy custom step is served with an icon
- **WHEN** a custom step named "Vehicle Info" exists with a stored null icon
  and an admin lists the branch's form steps
- **THEN** that step is returned with `icon` equal to `car`

### Requirement: The Admin Form Builder Renders a Glyph Matching Each Step Icon
The admin Form Builder step card SHALL render a distinct glyph that depicts
each vocabulary slug (for example a car for `car`, a briefcase for
`briefcase`), SHALL render a neutral glyph for an unrecognised slug, and
SHALL render the reorder drag handle with a grip glyph that is visually
distinct from every step icon.

#### Scenario: Vehicle step shows a car glyph
- **WHEN** the Form Builder displays a step whose `icon` is `car`
- **THEN** the step card shows a car glyph, not a grid glyph

#### Scenario: Drag handle is not mistaken for a step icon
- **WHEN** the Form Builder displays a reorderable step card
- **THEN** the drag handle shows a grip glyph that no step icon uses

#### Scenario: Unknown slug degrades gracefully
- **WHEN** the Form Builder displays a step whose `icon` is a slug outside
  the vocabulary
- **THEN** the step card shows the neutral default glyph
