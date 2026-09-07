## ADDED Requirements

### Requirement: Resolved File References Are Usable by an HTTP Client Regardless of Backend
When a feature resolves a stored file's key for inclusion in an API
response field intended for client-side rendering (e.g. a photo or badge
URL), the system SHALL return a reference the calling HTTP client can
fetch directly, regardless of which storage backend is active. This SHALL
hold for the local-disk backend as well as the S3-compatible backend — a
raw server-side filesystem path is never an acceptable resolved value for
a client-facing field, even when it is technically non-null.

#### Scenario: Local backend resolves to a fetchable URL
- **WHEN** the local-disk backend is active and a feature resolves a stored
  file's key for a client-facing response field
- **THEN** the resolved value is an HTTP URL that an authenticated client
  can fetch to retrieve the file's content, not a filesystem path

#### Scenario: S3-compatible backend resolves to a fetchable URL
- **WHEN** the S3-compatible backend is active and a feature resolves a
  stored file's key for a client-facing response field
- **THEN** the resolved value is a time-boxed, presigned URL an
  authenticated client can fetch to retrieve the file's content

#### Scenario: Switching backends does not change what the caller receives
- **WHEN** the storage backend configuration changes from local to
  S3-compatible (or vice versa) with no code change in the calling feature
- **THEN** the feature's response field continues to be a client-fetchable
  reference, with no backend-specific branching required in the caller
