## ADDED Requirements

### Requirement: A Published Form Is Always Served in the Current Field and Group Shape
A published form SHALL be returned in the current documented shape,
whenever it was published. This applies to the effective form used by the
visitor request and staff registration pages. Every field and group in
the response SHALL carry every key the current field and group schemas
define. A key missing from the stored snapshot SHALL be filled with that
key's documented default: a field's `hideLabel` is `false`, and a group's
`visibilityCondition` is `null`. Normalising SHALL NOT change any value
that the stored snapshot does carry.

#### Scenario: A form published before hideLabel existed still loads
- **WHEN** the effective form is requested and the published snapshot's
  fields have no `hideLabel` key and its groups have no
  `visibilityCondition` key
- **THEN** the response is 200, every field has `hideLabel: false`, every
  group has `visibilityCondition: null`, and every other value matches
  the snapshot

### Requirement: A Stored Field of an Unsupported Type Never Breaks Form Retrieval or Submission
A stored field row, or a field inside a published form snapshot, can
carry a field type outside the supported set, for example one removed
from the catalog after it was saved. When one does:
- every form-builder read SHALL omit that field and still return the rest
  of the form successfully. That covers the admin step list, step and
  field reads, and the effective form;
- a response SHALL NEVER contain a field type outside the supported set;
- the system SHALL log a `WARNING` identifying the field's id, key and
  stored type;
- submission validation SHALL treat such a field as absent. It SHALL NOT
  require a value for it, and SHALL NOT reject a submission because of it.

#### Scenario: Effective form with an unsupported field still loads
- **WHEN** the published tenant-default form contains a field of type
  `signature_pad` alongside supported fields, and the effective form is
  requested
- **THEN** the response is 200, contains every supported field, omits the
  `signature_pad` field, and a warning naming that field is logged

#### Scenario: Admin step list with an unsupported field still loads
- **WHEN** an admin with `form-builder:view` lists the steps of a form
  whose stored fields include one of type `signature_pad`
- **THEN** the response is 200 with every step and every supported field,
  rather than a 500

#### Scenario: Submission ignores an unsupported required field
- **WHEN** a registration is submitted against a published form containing
  a required field of an unsupported type, and no value is given for it
- **THEN** the submission is not rejected on account of that field

### Requirement: Stored Form Configuration Is Migrated to the Current Catalog and Shape
The system SHALL convert every stored field, and every field in every
published form snapshot, whose type is one of the removed types into a
supported type. It SHALL keep the field's id, key, label, help text,
required flag, width, order, step and group. The conversion SHALL be:
- `signature_pad` → `checkbox_single` (a consent checkbox), with options
  cleared;
- `rich_text_block` → `static_text`;
- `dynamic_table` → `textarea`, with options cleared.

The same migration SHALL add any missing `hideLabel` (default `false`) to
snapshot fields, and any missing `visibilityCondition` (default `null`) to
snapshot groups. It SHALL be idempotent, SHALL log each converted field,
and SHALL leave supported, complete fields untouched.

#### Scenario: Terms & Conditions signature field becomes a consent checkbox
- **WHEN** the migration runs on a tenant whose form has the optional
  field `terms_conditions` of type `signature_pad` with its terms text in
  the help text, both as a row and in the published default snapshot
- **THEN** both the row and the snapshot field have type
  `checkbox_single`, the same id, key, label and help text, remain
  optional, and have no options

#### Scenario: Old snapshot keys are backfilled
- **WHEN** the migration runs on a snapshot whose fields lack `hideLabel`
  and whose groups lack `visibilityCondition`
- **THEN** every field has `hideLabel: false` and every group has
  `visibilityCondition: null`, and no other value changes

#### Scenario: Re-running the migration changes nothing
- **WHEN** the migration runs a second time on the same tenant
- **THEN** no field or snapshot is modified
