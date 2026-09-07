## MODIFIED Requirements

### Requirement: Visitor and Primary Contact Registration Optionally Captures a Profile Photo
The system SHALL accept an optional profile photo file for the primary
contact and for each visitor entry (in both `individual` and `group`
registrations), submitted as an additional file part alongside the
existing ID-proof file(s) in the same `multipart/form-data` request,
order-matched to the visitor list the same way co-visitor ID-proof files
already are. The system SHALL validate the uploaded photo's actual content
against an image-only allow-list (JPEG/PNG) — never the client-supplied
content-type or filename alone — and SHALL enforce a maximum upload size,
consistent with the existing ID-proof validation rules ("Every Visitor Has
a Reachable Contact and a Validated ID Proof"). Omitting the photo for the
primary contact or any visitor SHALL NOT cause the request to be rejected —
the photo remains optional. Because `POST /registrations/walk-in` accepts
the identical payload/file contract as `POST /invitations` (see the
`registrations` capability), this optional photo capture applies to
walk-in registrations without any separate change to that endpoint. Every
photo URL returned by any invitation response (creation, detail, tracking,
check-in, check-out, list) SHALL be a fetchable HTTP URL an authenticated
client can retrieve the image content from, not merely a non-null string —
per the `file-storage` capability's requirement that a resolved reference
is usable by an HTTP client regardless of the active storage backend.

#### Scenario: Photo supplied and valid is stored and returned
- **WHEN** a creation request includes a valid JPEG or PNG photo for the
  primary contact
- **THEN** the request succeeds, the photo is stored, and the invitation's
  detail responses include a fetchable HTTP URL for it that an
  authenticated client can retrieve the image content from

#### Scenario: Photo omitted does not affect creation
- **WHEN** a creation request supplies no photo for the primary contact or
  any visitor
- **THEN** the request succeeds exactly as it would today, with no photo
  recorded for anyone who didn't supply one

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
  the primary contact and/or one or more visitors
- **THEN** the same validation and storage behavior applies, since it
  submits the identical payload/file contract as `POST /invitations`

## ADDED Requirements

### Requirement: Issued Badge Image Is Retrievable as a Fetchable URL
When a badge is issued or reprinted for an invitation, the response's
badge URL SHALL be a fetchable HTTP URL an authenticated client can
retrieve the badge image content from, not merely a non-null string —
consistent with the `file-storage` capability's requirement that a
resolved reference is usable by an HTTP client regardless of the active
storage backend.

#### Scenario: Issued badge URL is fetchable
- **WHEN** a badge is issued for an approved, checked-in invitation
- **THEN** the response's badge URL can be fetched by an authenticated
  client to retrieve the badge image content

#### Scenario: Reprinted badge URL is fetchable
- **WHEN** an already-issued badge is reprinted
- **THEN** the response's badge URL can be fetched by an authenticated
  client to retrieve the badge image content, whether or not it differs
  from the originally issued badge's URL
