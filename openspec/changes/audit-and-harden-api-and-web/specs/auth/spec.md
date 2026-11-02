## ADDED Requirements

### Requirement: The Current-User Profile Surfaces Effective Permission Codes
`GET /auth/me` SHALL include, on each of the caller's branch-role entries, a
`permissionCodes` list holding every permission code that role grants. A
client can then decide what to show from permissions rather than from role
names, so tenant-defined roles get the right UI. Existing fields SHALL be
unchanged.

#### Scenario: Standard role lists its permissions
- **WHEN** a Reception user calls `GET /auth/me`
- **THEN** their Reception branch-role entry includes `permissionCodes`
  containing `invitations:checkout`

#### Scenario: Tenant-defined role lists its permissions
- **WHEN** a user whose only role is a tenant-defined role granting
  `invitations:view-all` calls `GET /auth/me`
- **THEN** that branch-role entry's `permissionCodes` is exactly the
  role's granted codes

#### Scenario: Existing fields are unchanged
- **WHEN** any user calls `GET /auth/me`
- **THEN** `id`, `email`, `fullName`, `isActive`, `avatarUrl` and each
  branch role's `id`, `roleName` and `branchId` are returned as before
