## MODIFIED Requirements

### Requirement: An Admin Can Update an Existing Field's Description
The Field Properties panel SHALL let an admin add, change, or clear an
existing field's description, subject to the same locked-field restriction
already applied to that field's label and placeholder. An in-progress,
unsaved edit to the description SHALL survive a background refresh of that
same field's data — the panel only discards an unsaved draft when the admin
explicitly saves, explicitly resets, or switches to editing a different
field.

#### Scenario: Admin edits the description of an unlocked field
- **WHEN** an admin changes the description of an existing, unlocked field
  in the Field Properties panel and saves
- **THEN** the field's description is updated to the new value

#### Scenario: A locked field's description cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked field
- **THEN** the description input is disabled, consistent with that field's
  label and placeholder inputs, and no description change can be submitted
  for it

#### Scenario: An in-progress description edit is not overwritten by a background refresh
- **WHEN** an admin is typing or has pasted unsaved text into the
  description field, and the page's background field-list refresh completes
  while they are still editing (the same field's data, unchanged, refetched)
- **THEN** the description field keeps showing the admin's unsaved text, not
  the last-saved server value, and the admin can still save it

### Requirement: An Admin Can Edit an Existing Option-Bearing Field's Options
The Field Properties panel SHALL let an admin add, remove, rename, and
reorder the options of an existing `checkbox_list`, `dropdown_select`, or
optioned `toggle_switch` field after it has been created — not only at
field-creation time — subject to the same locked-field restriction already
applied to that field's label and placeholder. An in-progress, unsaved
change to the options list SHALL survive a background refresh of that same
field's data — the panel only discards an unsaved draft when the admin
explicitly saves, explicitly resets, or switches to editing a different
field.

#### Scenario: Admin adds an option to an existing unlocked checkbox list field
- **WHEN** an admin adds a new option to an existing, unlocked
  `checkbox_list` field in the Field Properties panel and saves
- **THEN** the new option is added to the field's option list and appears
  as a selectable choice on the visitor-facing form

#### Scenario: Admin removes or renames an option on an existing unlocked field
- **WHEN** an admin removes or renames an option of an existing, unlocked
  `checkbox_list` or `dropdown_select` field and saves
- **THEN** the field's option list reflects the removal or rename

#### Scenario: Clearing every option from an option-required field type is rejected
- **WHEN** an admin removes all options from a `checkbox_list` or
  `dropdown_select` field and attempts to save
- **THEN** the save is rejected and the admin UI surfaces the "must declare
  a non-empty options list" error, and the field's previously saved options
  are left unchanged

#### Scenario: A locked field's options cannot be edited
- **WHEN** an admin opens the Field Properties panel for a locked,
  option-bearing field
- **THEN** the options editor is disabled, consistent with that field's
  label and placeholder inputs, and no option change can be submitted for it

#### Scenario: An in-progress options edit is not overwritten by a background refresh
- **WHEN** an admin has added, removed, or reordered options in the editor
  without saving yet, and the page's background field-list refresh completes
  while they are still editing (the same field's data, unchanged, refetched)
- **THEN** the options editor keeps showing the admin's unsaved draft, not
  the last-saved server value, and the admin can still save it
