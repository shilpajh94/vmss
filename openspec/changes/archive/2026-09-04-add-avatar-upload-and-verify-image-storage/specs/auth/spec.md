## ADDED Requirements

### Requirement: User Can Upload and View Their Own Profile Picture
An authenticated user SHALL be able to upload a profile picture (avatar)
for their own account via a dedicated endpoint. The system SHALL validate
the uploaded file's actual content against an image-only allow-list
(JPEG/PNG) — never the client-supplied content type or filename alone —
and SHALL enforce a maximum upload size, consistent with the validation
rules already established for other file uploads in this system. On
success, the resulting reference SHALL be persisted on the user's account
and SHALL be returned as a fetchable URL both from the caller's own
profile endpoint and from any employee-listing endpoint that already
exposes other employees' profile pictures.

#### Scenario: Valid avatar upload succeeds and is retrievable
- **WHEN** an authenticated user uploads a valid JPEG or PNG as their
  avatar
- **THEN** the upload succeeds, and the user's own profile endpoint
  subsequently returns a fetchable URL for it

#### Scenario: Disguised executable submitted as an avatar is rejected
- **WHEN** an uploaded avatar file's real content does not match an
  allowed image format, regardless of its filename extension or declared
  content type
- **THEN** the system rejects the file and the user's existing avatar (if
  any) is left unchanged

#### Scenario: Oversized avatar upload is rejected
- **WHEN** an uploaded avatar file exceeds the configured maximum size
- **THEN** the system rejects the file before buffering the full upload
  into memory, and the user's existing avatar (if any) is left unchanged

#### Scenario: Uploading a new avatar replaces the previous one
- **WHEN** a user who already has an avatar uploads a new valid one
- **THEN** the user's profile endpoint returns a fetchable URL for the new
  avatar, not the previous one

#### Scenario: A user with no avatar uploaded has no avatar URL
- **WHEN** a user who has never uploaded an avatar is returned by their own
  profile endpoint or an employee-listing endpoint
- **THEN** the avatar URL field is absent or null, and no error occurs

#### Scenario: Employee directory listing surfaces the same avatar field as other employee listings
- **WHEN** a user with an avatar is returned by the employee directory
  listing endpoint
- **THEN** the response includes the same fetchable avatar URL field that
  other employee-listing endpoints already return for that user
