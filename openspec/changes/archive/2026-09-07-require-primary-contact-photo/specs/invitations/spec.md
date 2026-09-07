## MODIFIED Requirements

### Requirement: Visitor and Primary Contact Registration Optionally Captures a Profile Photo
The system SHALL require a profile photo file for the primary contact on
every invitation-creation and walk-in-registration request — submitted as
a mandatory additional file part (`primaryContactPhotoFile`) alongside the
existing ID-proof file(s) in the same `multipart/form-data` request. A
request that omits the primary contact's photo SHALL be rejected with a
validation error before any invitation or registration record is created,
the same way an omitted primary-contact ID-proof file already is. The
system SHALL validate the uploaded photo's actual content against an
image-only allow-list (JPEG/PNG) — never the client-supplied content-type
or filename alone — and SHALL enforce a maximum upload size, consistent
with the existing ID-proof validation rules ("Every Visitor Has a
Reachable Contact and a Validated ID Proof"). Each co-visitor entry's
profile photo remains optional and order-matched to the visitor list the
same way co-visitor ID-proof files already are; omitting a co-visitor's
photo SHALL NOT cause the request to be rejected. Because
`POST /registrations/walk-in` accepts the identical payload/file contract
as `POST /invitations` (see the `registrations` capability), this
mandatory primary-contact photo capture applies to walk-in registrations
without any separate change to that endpoint. Every photo URL returned by
any invitation response (creation, detail, tracking, check-in, check-out,
list) SHALL be a fetchable HTTP URL an authenticated client can retrieve
the image content from, not merely a non-null string — per the
`file-storage` capability's requirement that a resolved reference is
usable by an HTTP client regardless of the active storage backend.

#### Scenario: Photo supplied and valid is stored and returned
- **WHEN** a creation request includes a valid JPEG or PNG photo for the
  primary contact
- **THEN** the request succeeds, the photo is stored, and the invitation's
  detail responses include a fetchable HTTP URL for it that an
  authenticated client can retrieve the image content from

#### Scenario: Missing primary contact photo is rejected
- **WHEN** a creation request omits the primary contact's photo file
- **THEN** the request is rejected with a validation error and no
  invitation or registration record is created

#### Scenario: Photo omitted does not affect creation
- **WHEN** a `group` creation request supplies no photo for one or more
  co-visitors (but does supply the now-mandatory primary contact photo)
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
- **WHEN** a caller submits `POST /registrations/walk-in` with a photo for
  the primary contact and, optionally, one or more visitors, or omits a
  co-visitor's photo
- **THEN** the same validation and storage behavior applies as
  `POST /invitations`, since it submits the identical payload/file
  contract — including the mandatory primary contact photo requirement
  (see "Missing primary contact photo is rejected")
