## ADDED Requirements

### Requirement: Kiosk Record
The system SHALL store a tenant-scoped `Kiosk` with `name` (required, max 255),
`description` (optional, max 2000), `is_active` (default true), `is_hidden`
(default false), and soft-delete via `deleted_at`.

#### Scenario: Admin creates a kiosk
- **WHEN** a caller with `kiosks:manage` POSTs a valid `name` and optional `description` to `/api/v1/kiosks`
- **THEN** the kiosk is persisted with `isActive=true` and `isHidden=false` and returned with 201

#### Scenario: Duplicate name is rejected
- **WHEN** a kiosk is created or renamed to a name already used (case-insensitive) by a non-deleted kiosk
- **THEN** the request is rejected with 409

#### Scenario: Deleted kiosk's name is reusable
- **WHEN** a kiosk is soft-deleted and another kiosk is created with the same name
- **THEN** the creation succeeds

### Requirement: Kiosk Listing With Hidden Filtering
The system SHALL list kiosks with the standard `page`/`pageSize` pagination,
whitelisted `sortBy`/`sortOrder`, and an `isActive`-style `status` filter, and
SHALL exclude soft-deleted and hidden kiosks unless `includeHidden=true`.

#### Scenario: Default list omits hidden kiosks
- **WHEN** a caller with `kiosks:view` lists kiosks without `includeHidden`
- **THEN** only non-deleted, non-hidden kiosks are returned

#### Scenario: Hidden kiosks are opt-in
- **WHEN** the caller passes `includeHidden=true`
- **THEN** hidden (but not deleted) kiosks are included in the results

#### Scenario: Invalid sort column
- **WHEN** `sortBy` is not in the whitelist
- **THEN** the request is rejected with 422

### Requirement: Kiosk Retrieval and Update
The system SHALL allow retrieving one kiosk by id (including hidden ones) and
partially updating its `name`, `description`, and `isActive`.

#### Scenario: Get a hidden kiosk by id
- **WHEN** a caller with `kiosks:view` requests a hidden, non-deleted kiosk by id
- **THEN** it is returned with 200

#### Scenario: Update kiosk
- **WHEN** a caller with `kiosks:manage` PUTs changed fields
- **THEN** only the supplied fields change and the updated kiosk is returned

#### Scenario: Unknown or deleted kiosk
- **WHEN** the id does not exist or the kiosk is soft-deleted
- **THEN** the response is 404

### Requirement: Hide and Unhide Kiosk
The system SHALL let a caller with `kiosks:manage` set `isHidden` on a kiosk via
`PATCH /api/v1/kiosks/{id}/visibility`. Hiding SHALL NOT change `isActive` or
delete the record.

#### Scenario: Hide a kiosk
- **WHEN** the caller PATCHes `{"isHidden": true}`
- **THEN** the kiosk is returned with `isHidden=true`, `isActive` unchanged, and it no longer appears in the default list

#### Scenario: Unhide a kiosk
- **WHEN** the caller PATCHes `{"isHidden": false}`
- **THEN** the kiosk reappears in the default list

### Requirement: Kiosk Soft Delete
The system SHALL soft-delete a kiosk via `DELETE /api/v1/kiosks/{id}`, setting
`deleted_at` and returning 204.

#### Scenario: Delete kiosk
- **WHEN** a caller with `kiosks:manage` deletes an existing kiosk
- **THEN** the response is 204, the row remains with `deleted_at` set, and subsequent get/list no longer return it

### Requirement: Kiosk Endpoints Are Admin-Authenticated and Audited
Every kiosk endpoint SHALL require a valid bearer token and the relevant
permission (`kiosks:manage` for writes, `kiosks:view` for reads); none is
public. Each create, update, hide/unhide, and delete SHALL write an audit-log
entry via a background task.

#### Scenario: Unauthenticated caller
- **WHEN** a kiosk endpoint is called without a valid token
- **THEN** the response is 401

#### Scenario: Missing permission
- **WHEN** a caller lacking `kiosks:manage` calls a write endpoint
- **THEN** the response is 403

#### Scenario: Mutation is audited
- **WHEN** a kiosk is created, updated, hidden/unhidden, or deleted
- **THEN** an audit entry (`kiosk_created`, `kiosk_updated`, `kiosk_hidden`/`kiosk_unhidden`, `kiosk_deleted`) is recorded with entity type `Kiosk`

#### Scenario: Tenant isolation
- **WHEN** a kiosk exists in tenant A's schema
- **THEN** it is never returned to a session bound to tenant B's schema
