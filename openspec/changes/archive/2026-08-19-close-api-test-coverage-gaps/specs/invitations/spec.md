## MODIFIED Requirements

### Requirement: Each Visitor Has at Least One Reachable Contact and an ID Proof
Every visitor entry (the primary contact and each co-visitor in a group) SHALL provide at
least one of email or phone, an ID proof type from the supported set (Aadhaar Card, Passport,
Driving License, Other), and an accompanying ID proof file. The system SHALL validate the
uploaded file's actual content against an image/PDF allow-list, not merely the client-supplied
content type or file extension, and SHALL enforce a maximum upload size. The system SHALL
validate every visitor's ID proof file before persisting any of them to storage, so that a
submission rejected because one visitor's file fails validation leaves no other visitor's
file written to storage.

#### Scenario: Visitor with neither email nor phone rejected
- **WHEN** a visitor entry supplies neither an email nor a phone number
- **THEN** the system rejects the submission with a validation error

#### Scenario: Disguised executable rejected
- **WHEN** an uploaded ID proof file's real content does not match an allowed image/PDF
  format, regardless of its filename extension or declared content type
- **THEN** the system rejects the file and the overall submission

#### Scenario: Oversized upload rejected
- **WHEN** an uploaded ID proof file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload into memory

#### Scenario: Earlier visitor's file not persisted when a later visitor's file is rejected
- **WHEN** a group submission's first visitor supplies a valid ID proof file and a later
  visitor's ID proof file fails content validation
- **THEN** the system rejects the entire submission and does not write the first visitor's
  file to storage
