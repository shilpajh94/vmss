## MODIFIED Requirements

### Requirement: Every Visitor Has a Reachable Contact and a Validated ID Proof
Every visitor entry (the primary contact and each co-visitor in a group)
SHALL provide at least one of email or phone, an ID proof type, and an
accompanying ID proof file. A supplied ID proof type SHALL be one of the
calling branch's currently configured Visitor Info "ID Proof Type"
options (Form Builder) — not a fixed set baked into the API — so an admin
can add, remove, or rename ID proof type choices without a code change.
The system SHALL validate each uploaded file's actual content against an
image/PDF allow-list, not merely the client-supplied content type or file
extension, and SHALL enforce a maximum upload size. The system SHALL
validate every visitor's ID proof file before persisting any of them to
storage, so that a request rejected because one visitor's file fails
validation leaves no other visitor's file written to storage.

#### Scenario: Visitor with neither email nor phone rejected
- **WHEN** a visitor entry supplies neither an email nor a phone number
- **THEN** the system rejects the request with a validation error

#### Scenario: An ID proof type outside the branch's configured options is rejected
- **WHEN** a visitor entry's `idProofType` is not one of the calling
  branch's currently configured "ID Proof Type" options
- **THEN** the system rejects the request with a validation error

#### Scenario: A branch-customized ID proof type option is accepted
- **WHEN** an admin adds a new option (e.g. "Voter ID") to the branch's "ID
  Proof Type" field and publishes, and a visitor entry supplies that new
  option as its `idProofType`
- **THEN** the system accepts the request

#### Scenario: Disguised executable rejected
- **WHEN** an uploaded ID proof file's real content does not match an
  allowed image/PDF format, regardless of its filename extension or
  declared content type
- **THEN** the system rejects the file and the overall request

#### Scenario: Oversized upload rejected
- **WHEN** an uploaded ID proof file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload into
  memory

#### Scenario: Earlier visitor's file not persisted when a later visitor's file is rejected
- **WHEN** a group request's first visitor supplies a valid ID proof file
  and a later visitor's ID proof file fails content validation
- **THEN** the system rejects the entire request and does not write the
  first visitor's file to storage

### Requirement: Carried Items and Vehicles Are Optional Structured Declarations
The system SHALL accept zero or more carried-item declarations (each an item
category plus an optional free-text description) and zero or more vehicle
declarations (each a vehicle type, license plate, make/model, and color),
and SHALL accept a request that declares neither. A declared vehicle's
vehicle type SHALL be one of the calling branch's currently configured
Vehicle Info "Vehicle Type" options (Form Builder) — not a fixed set baked
into the API — so an admin can add, remove, or rename vehicle type choices
without a code change.

#### Scenario: Request with no items or vehicles accepted
- **WHEN** a creation request omits carried items and vehicles entirely
- **THEN** the system accepts the request as long as all other requirements
  are met

#### Scenario: Multiple vehicles recorded
- **WHEN** a creation request lists more than one vehicle
- **THEN** the system stores each vehicle as a separate record linked to the
  invitation

#### Scenario: A vehicle type outside the branch's configured options is rejected
- **WHEN** a vehicle declaration's `vehicleType` is not one of the calling
  branch's currently configured "Vehicle Type" options
- **THEN** the system rejects the request with a validation error

#### Scenario: A branch-customized vehicle type option is accepted
- **WHEN** an admin adds a new option to the branch's "Vehicle Type" field
  and publishes, and a vehicle declaration supplies that new option as its
  `vehicleType`
- **THEN** the system accepts the request
