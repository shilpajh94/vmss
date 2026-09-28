## MODIFIED Requirements

### Requirement: Role Permission Codes Must Exist in the Catalog
The system SHALL reject a role create or update request that references a
permission code not present in the global permission catalog, and SHALL
provide a read-only endpoint for a caller with `roles:view` to retrieve the
list of valid permission codes for their tenant, so a role-creation or
role-update form can be populated with codes known to be valid before
submission. That endpoint SHALL accept `page` and `page_size` query
parameters (page 1-indexed, page size defaulting to 20 with a maximum of
100) and a `sort_by`/`sort_order` pair (whitelisted to `code`, defaulting to
`code` ascending), and SHALL return the catalog wrapped in a paginated
envelope carrying `page`, `pageSize`, `total`, and `totalPages`, matching the
shape already returned by the sibling roles-list endpoint, rather than a
bare array.

#### Scenario: Creating a role with an unknown permission code is rejected
- **WHEN** a caller submits a role create or update request containing a
  permission code that does not exist in the catalog
- **THEN** the request is rejected with 404 and no role is created or
  modified

#### Scenario: Permission catalog is retrievable
- **WHEN** a caller with `roles:view` requests the permission catalog
- **THEN** the response lists every permission code the tenant's roles can
  be granted, in a form a client can use directly as the choices for a
  role-creation or role-update form's permission-code field

#### Scenario: Permission catalog is paginated
- **WHEN** a caller with `roles:view` requests the permission catalog with
  no `page`/`page_size` supplied
- **THEN** the response returns the first page (up to 20 permission codes)
  wrapped in a pagination block reporting `page: 1` and the correct `total`
  and `totalPages` for the tenant's full catalog size

#### Scenario: Permission catalog page beyond the last page is empty, not an error
- **WHEN** a caller requests a `page` number past the last page the current
  catalog size produces
- **THEN** the response returns an empty `data` array with the same
  pagination block shape, rather than a 404 or 400

## ADDED Requirements

### Requirement: Employee Directory Supports a Status Filter
`GET /employees` SHALL accept an optional `status` query filter
(`active`/`inactive`, mapped onto `User.is_active`), applying no filter
when omitted and combinable with the endpoint's existing `departmentId`,
`email`, and `role` filters (`AND` semantics).

#### Scenario: Filtering employees by status
- **WHEN** a caller requests `GET /employees?status=inactive`
- **THEN** only employees with `is_active=false` are returned

#### Scenario: Status filter combines with existing filters
- **WHEN** a caller requests `GET /employees?role=Receptionist&status=active`
- **THEN** only active employees holding the Receptionist role are returned
