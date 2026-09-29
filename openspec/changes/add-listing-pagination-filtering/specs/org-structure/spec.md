## ADDED Requirements

### Requirement: Master-Data List Endpoints Support Typed Attribute Filters
In addition to the existing parent-scope filters (`buildingId` on
`/floors`/`/security-gates`, `floorId` on `/departments`/`/reception-desks`)
and `X-Branch-ID`, the six master-data list endpoints SHALL accept the
following typed, whitelisted query filters, each optional and, when
omitted, applying no filter:
- `GET /branches`: `status` (`active`/`inactive`, `Branch.is_active`).
- `GET /buildings`: `status` (`active`/`inactive`, `Building.is_active`).
- `GET /floors`: `status` (`active`/`inactive`, `Floor.is_active`) and
  `accessLevel` (`public`/`restricted`/`secure`, `Floor.access_level`).
- `GET /departments`: `status` (`active`/`inactive`, `Department.is_active`).
- `GET /reception-desks`: `status` (`active`/`maintenance`/`inactive`,
  `ReceptionDesk.status`).
- `GET /security-gates`: `gateType` (`entry`/`exit`/`both`,
  `SecurityGate.gate_type`) and `securityLevel` (`standard`/`high`, mapped
  onto `SecurityGate.high_security`).

An unrecognized filter value SHALL be rejected with 422 (standard FastAPI
enum-validation behavior), not silently ignored. Combining a typed filter
with an existing parent-scope filter or `X-Branch-ID` SHALL narrow by all
of them at once (AND semantics), matching how the parent-scope filters
already combine with branch scope.

#### Scenario: Filtering branches by status
- **WHEN** a caller requests `GET /branches?status=inactive`
- **THEN** only branches with `is_active=false` are returned

#### Scenario: Filtering floors by access level
- **WHEN** a caller requests `GET /floors?accessLevel=restricted`
- **THEN** only floors whose `access_level` is `restricted` are returned

#### Scenario: Filtering reception desks by status
- **WHEN** a caller requests `GET /reception-desks?status=maintenance`
- **THEN** only reception desks whose `status` is `maintenance` are returned

#### Scenario: Filtering security gates by gate type and security level
- **WHEN** a caller requests `GET /security-gates?gateType=exit&securityLevel=high`
- **THEN** only security gates whose `gate_type` is `exit` and whose
  `high_security` is `true` are returned

#### Scenario: Filters combine with existing parent-scope filters
- **WHEN** a caller requests `GET /departments?floorId=<id>&status=active`
- **THEN** only active departments belonging to that floor are returned

#### Scenario: Unrecognized filter value is rejected
- **WHEN** a caller requests one of these endpoints with a filter query
  param set to a value outside its whitelisted enum (e.g.
  `GET /security-gates?gateType=side`)
- **THEN** the request is rejected with 422 and no filtering is applied
