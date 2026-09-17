## MODIFIED Requirements

### Requirement: ID-proof document image and profile photo are read from prefill for reuse
The system SHALL read the ID-proof document image URL and profile photo URL from the visitor-portal lookup's prefill profile, when present, and make them available to the visitor request wizard so the returning visitor can choose to reuse them instead of always uploading fresh files.

#### Scenario: ID-proof and photo URLs are made available to the wizard
- **WHEN** the lookup's prefill profile includes an ID-proof document image URL and/or a profile photo URL
- **THEN** the system passes those URLs into the visitor request wizard's initial data alongside the other prefill fields (full name, email, phone, ID-proof type)

#### Scenario: Missing prefill file URL falls back to fresh upload
- **WHEN** the lookup's prefill profile omits the ID-proof document image URL or the profile photo URL (e.g. the visitor never previously supplied one)
- **THEN** the wizard's corresponding field has no existing file to reuse and behaves as it does for a first-time visitor, requiring a fresh upload
