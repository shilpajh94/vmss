## MODIFIED Requirements

### Requirement: General Information section captures organisation name and default timezone
The system SHALL let an admin edit the organisation name in a text field and choose the default timezone from a list of IANA time zones (for example `Asia/Kolkata`), each labelled with its current UTC offset. The value saved SHALL be the IANA zone name. When the stored value is a legacy UTC-offset string (for example `GMT+05:30`), the list SHALL preselect a zone with that offset, and saving SHALL store that zone's IANA name. The organisation name SHALL NOT be saved blank.

#### Scenario: Admin edits organisation name
- **WHEN** an admin changes the text in the "Organisation Name" field
- **THEN** the field reflects the newly entered text as unsaved

#### Scenario: Admin changes default timezone
- **WHEN** an admin selects a different value from the "Default Timezone" list
- **THEN** the field reflects the newly selected timezone as unsaved, and saving sends its IANA zone name

#### Scenario: Legacy offset value is upgraded on save
- **WHEN** the stored timezone is `GMT+05:30` and the admin saves the configuration
- **THEN** the saved value is an IANA zone name with a +05:30 offset

#### Scenario: Blank organisation name
- **WHEN** an admin clears the organisation name and saves
- **THEN** an inline error is shown and nothing is saved

## REMOVED Requirements

### Requirement: Filters affordance is presented but not yet functional
**Reason**: Dead UI. The page has nothing to filter.
**Migration**: None. The control is removed.

### Requirement: Organisation logo can be uploaded with type and size validation
**Reason**: The picker only previewed the file locally. The API has no
logo-upload endpoint, so a "successful" upload was silently discarded on
save. Tenant branding is tracked as gap register G13
(`add-tenant-branding`).
**Migration**: None for users. The logo picker returns when branding is
built.
