## MODIFIED Requirements

### Requirement: Every Visitor Has a Reachable Contact and a Validated ID Proof
Every visitor entry (the primary contact and each co-visitor in a group)
SHALL provide at least one of email or phone. Whether an ID proof type and
an accompanying ID proof file are required is determined by the calling
branch's published `form-builder` configuration for the Visitor Info step's
ID-proof-type and ID-proof-upload fields (locked-required by default; an
admin may deactivate or make either optional per branch). When required,
the system SHALL validate each uploaded file's actual content against an
image/PDF allow-list, not merely the client-supplied content type or file
extension, and SHALL enforce a maximum upload size. The system SHALL
validate every visitor's ID proof file before persisting any of them to
storage, so that a request rejected because one visitor's file fails
validation leaves no other visitor's file written to storage.

#### Scenario: Visitor with neither email nor phone rejected
- **WHEN** a visitor entry supplies neither an email nor a phone number
- **THEN** the system rejects the request with a validation error

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

#### Scenario: ID proof not required when the branch has deactivated it
- **WHEN** the calling branch's published configuration marks the ID-proof-
  type/upload fields inactive
- **THEN** a submission omitting ID proof type and file is accepted, subject
  to every other applicable requirement

### Requirement: Visitor and Primary Contact Registration Optionally Captures a Profile Photo
Whether a profile photo is required for the primary contact is determined by
the calling branch's published `form-builder` configuration for the
Visitor Info step's profile-photo field (active-and-required by default,
matching today's behavior; an admin may deactivate it or make it optional
per branch). When required, it is submitted as a mandatory additional file
part (`primaryContactPhotoFile`) alongside the existing ID-proof file(s) in
the same `multipart/form-data` request, and a request omitting it SHALL be
rejected before any invitation or registration record is created — the same
way an omitted mandatory primary-contact ID-proof file already is. The
system SHALL validate the uploaded photo's actual content against an
image-only allow-list (JPEG/PNG) — never the client-supplied content-type
or filename alone — and SHALL enforce a maximum upload size, consistent
with the existing ID-proof validation rules ("Every Visitor Has a
Reachable Contact and a Validated ID Proof"). Each co-visitor entry's
profile photo remains optional regardless of branch configuration and
order-matched to the visitor list the same way co-visitor ID-proof files
already are; omitting a co-visitor's photo SHALL NOT cause the request to
be rejected. Because `POST /registrations/walk-in` accepts the identical
payload/file contract as `POST /invitations` (see the `registrations`
capability), this branch-configured primary-contact photo requirement
applies to walk-in registrations without any separate change to that
endpoint. Every photo URL returned by any invitation response (creation,
detail, tracking, check-in, check-out, list) SHALL be a fetchable HTTP URL
an authenticated client can retrieve the image content from, not merely a
non-null string — per the `file-storage` capability's requirement that a
resolved reference is usable by an HTTP client regardless of the active
storage backend.

#### Scenario: Photo supplied and valid is stored and returned
- **WHEN** a creation request includes a valid JPEG or PNG photo for the
  primary contact
- **THEN** the request succeeds, the photo is stored, and the invitation's
  detail responses include a fetchable HTTP URL for it that an
  authenticated client can retrieve the image content from

#### Scenario: Missing primary contact photo is rejected
- **WHEN** a creation request omits the primary contact's photo file, and
  the calling branch's published configuration marks the profile-photo
  field required (the default)
- **THEN** the request is rejected with a validation error and no
  invitation or registration record is created

#### Scenario: Missing primary contact photo is accepted when the branch has deactivated it
- **WHEN** a creation request omits the primary contact's photo file, and
  the calling branch's published configuration marks the profile-photo
  field inactive or optional
- **THEN** the request is not rejected for the missing photo, subject to
  every other applicable requirement

#### Scenario: Photo omitted does not affect creation
- **WHEN** a `group` creation request supplies no photo for one or more
  co-visitors (regardless of whether the primary contact's photo was
  required and supplied)
- **THEN** the request succeeds, with no photo recorded for any co-visitor
  who didn't supply one

#### Scenario: Disguised executable submitted as a photo is rejected
- **WHEN** an uploaded photo file's real content does not match an allowed
  image format, regardless of its filename extension or declared content
  type
- **THEN** the system rejects the file and the overall request, creating no
  invitation record

#### Scenario: Oversized photo upload is rejected
- **WHEN** an uploaded photo file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload
  into memory

#### Scenario: Walk-in registration inherits the same optional photo capture
- **WHEN** a caller submits `POST /registrations/walk-in` with or without a
  photo for the primary contact and, optionally, one or more visitors
- **THEN** the same validation and storage behavior applies as
  `POST /invitations`, since it submits the identical payload/file
  contract, including whatever the resolved branch's photo requirement is

### Requirement: Consent Is Mandatory and Recorded
An invitation SHALL be created only if the primary contact has accepted
every consent field the calling branch's published `form-builder`
configuration marks required in the Consent Agreement step. The set of
consent statements, and which are required, is admin-configured per branch
(defaulting to the three consents — terms and conditions, data processing,
and safety guidelines — for every branch until an admin changes them). The
system SHALL record what was consented to and when.

#### Scenario: Missing consent rejected
- **WHEN** a creation request omits acceptance of, or sets to false, any
  consent the calling branch's published configuration marks required
- **THEN** the system rejects the request and creates no invitation record

#### Scenario: Full consent accepted and timestamped
- **WHEN** a creation request accepts every consent the calling branch's
  published configuration marks required
- **THEN** the system stores each accepted consent's key and value along
  with the timestamp consent was recorded

#### Scenario: Default consents preserved for an unconfigured branch
- **WHEN** a branch has never had its form configuration customized
- **THEN** its effective Consent Agreement step requires exactly the three
  default consents, matching pre-`form-builder` behavior

### Requirement: Carried Items and Vehicles Are Optional Structured Declarations
The system SHALL accept zero or more carried-item declarations and zero or
more vehicle declarations, and SHALL accept a request that declares
neither. The set of valid carried-item entries (replacing the fixed
`CarriedItemCategory` enum) and the set of vehicle fields beyond the always-
required `vehicleType` and `licensePlate` are determined by the calling
branch's published `form-builder` configuration for the Carried Items and
Vehicle Info steps respectively (defaulting to today's fixed field sets for
every branch until an admin changes them).

#### Scenario: Request with no items or vehicles accepted
- **WHEN** a creation request omits carried items and vehicles entirely
- **THEN** the system accepts the request as long as all other requirements
  are met

#### Scenario: Carried-item entry outside the branch's configured set rejected
- **WHEN** a creation request declares a carried item whose key is not
  among the calling branch's published Carried Items configuration
- **THEN** the system rejects the request with a validation error

#### Scenario: Vehicle entry missing its locked fields rejected
- **WHEN** an entry in `vehicles` omits `vehicleType` or `licensePlate`
- **THEN** the system rejects the request with a validation error,
  regardless of the branch's Vehicle Info configuration

#### Scenario: Default carried-item and vehicle fields preserved for an unconfigured branch
- **WHEN** a branch has never had its form configuration customized
- **THEN** its effective Carried Items and Vehicle Info steps accept exactly
  today's fixed field sets, matching pre-`form-builder` behavior

#### Scenario: Multiple vehicles recorded
- **WHEN** a creation request lists more than one vehicle
- **THEN** the system stores each vehicle as a separate record linked to the
  invitation

### Requirement: Invitation Creation's Mandatory Fields Are Documented and Test-Verified
The system SHALL document, in `POST /invitations`'s `payload` field
description, which top-level and nested fields are structurally mandatory
(present on every request regardless of branch configuration — e.g.
`registrationType`, `primaryContact`, `visitDetails`, `consents`,
`fullName`, `licensePlate`) versus branch-configurable (whose required-ness
depends on the calling branch's published `form-builder` configuration —
e.g. ID proof, profile photo, expected duration, carried items, individual
consent statements), and SHALL reject a request missing any structurally
mandatory top-level field with a 422.

#### Scenario: Missing a required top-level field is rejected
- **WHEN** a creation request omits `registrationType`, `primaryContact`,
  `visitDetails`, or `consents` entirely
- **THEN** the system rejects the request with a 422 validation error,
  regardless of branch configuration

#### Scenario: Invalid enum value is rejected
- **WHEN** a creation request supplies a value for `registrationType` or
  `vehicleType` that is not one of the supported enum values, or a value
  for `idProofType` or a carried-item key that is not among the calling
  branch's published configuration
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: A vehicle or visitor missing its own required field is rejected
- **WHEN** an entry in `vehicles` omits `licensePlate`, or an entry in
  `visitors` omits `fullName`
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Documented required fields match the schema
- **WHEN** the `payload` field's description is compared against each
  nested Pydantic schema's own `model_json_schema()["required"]` list for
  the fields that are structurally mandatory (not branch-configurable)
- **THEN** every field the description calls structurally mandatory is
  actually required by its schema, and vice versa
