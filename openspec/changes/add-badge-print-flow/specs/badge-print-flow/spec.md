## ADDED Requirements

### Requirement: Badge Print Flow Is Gated by a Global and a Per-Tenant Flag
Every endpoint under `/api/v1/checkin` that belongs to the badge print flow SHALL respond `404` when `settings.badge_print_flow_enabled` is `false` or the caller's tenant has `badge_print_flow_enabled = false`. The flow is enabled only when both are true. The global setting SHALL default to `false`, and a new tenant SHALL default to `false`. With the flow off, the behavior of every pre-existing endpoint, message and badge SHALL be unchanged.

#### Scenario: Global flag off
- **WHEN** `BADGE_PRINT_FLOW_ENABLED` is `false` and an authorized caller requests any badge-flow endpoint
- **THEN** the response is `404`

#### Scenario: Tenant flag off
- **WHEN** the global flag is `true` and the caller's tenant has the toggle off
- **THEN** the response is `404`

#### Scenario: Both flags on
- **WHEN** both are true and the caller is authorized
- **THEN** the endpoint runs normally

#### Scenario: Existing flows unchanged with the flag off
- **WHEN** the flow is off and a caller uses `POST /invitations/{id}/badge`, the invitation check-in endpoints, or receives an approval message
- **THEN** behavior and payloads are identical to before this change

### Requirement: Admin Toggles the Flow Per Tenant
`PATCH /api/v1/tenants/me/settings` SHALL let a caller holding `tenants:update` set `badgePrintFlowEnabled` for their own tenant. `GET /api/v1/tenants/me` SHALL return the current value. The tenant is resolved from the token, never from the request.

#### Scenario: Admin enables the flow
- **WHEN** an Admin sends `{"badgePrintFlowEnabled": true}`
- **THEN** the tenant's toggle is stored, an audit entry is written, and `GET /tenants/me` returns `true`

#### Scenario: Caller without tenants:update is rejected
- **WHEN** a Reception user sends the same request
- **THEN** the response is `403` and nothing changes

### Requirement: Reception Searches Visits
`GET /api/v1/checkin/search` SHALL accept `q` (1 to 255 characters) and return visits the caller may see at their authorized branches, matching `q` against visitor name, phone (digits-only comparison), invitation code (`trackingId`), or numeric check-in code. It SHALL require `visitors:print_badge`, be paginated per `api-conventions.md`, and be read-only. A numeric check-in code or `trackingId` match SHALL be exact; name SHALL be a case-insensitive contains match.

#### Scenario: Search by phone
- **WHEN** reception searches `+91 95442-32271` and a visit is stored with `9544232271`-style digits
- **THEN** that visit is returned

#### Scenario: Search by check-in code
- **WHEN** reception searches an 8-character check-in code
- **THEN** the single matching visit is returned

#### Scenario: Other branch is not returned
- **WHEN** the only match is at a branch the caller is not authorized for
- **THEN** the result list is empty

#### Scenario: Permission denied
- **WHEN** a caller without `visitors:print_badge` searches
- **THEN** the response is `403`

### Requirement: Reception Confirms the Visitor's ID
`POST /api/v1/checkin/{visit_id}/verify-id` SHALL record `id_verified_at` and `id_verified_by_user_id` on the visit. It SHALL require `visitors:print_badge` and be audited. It SHALL be idempotent: repeating it keeps the original timestamp.

#### Scenario: ID confirmed
- **WHEN** reception calls the endpoint for an approved visit
- **THEN** the visit shows `idVerifiedAt` and the verifier

#### Scenario: Repeat call keeps the original timestamp
- **WHEN** the endpoint is called twice
- **THEN** `idVerifiedAt` is unchanged by the second call

### Requirement: Print Gate
A badge SHALL be printed only when the visit is `approved` or `checked_in`, a photo has been captured, and the ID is verified. Otherwise the request SHALL be rejected with `409` naming every unmet condition.

#### Scenario: All conditions met
- **WHEN** the visit is approved, has a photo and a verified ID
- **THEN** printing succeeds

#### Scenario: Missing photo and ID
- **WHEN** a visit has neither
- **THEN** the response is `409` listing `photo_missing` and `id_not_verified`

#### Scenario: Visit not approved
- **WHEN** the visit is `submitted` or `denied`
- **THEN** the response is `409`

### Requirement: Badge QR Token Is Signed, Day-Bound and Revocable
Each print SHALL create a badge QR token generated at reception, signed with a key distinct from the invitation QR key, carrying the visit id, tenant id, the tenant-local date it was printed on, and a unique `jti`. It SHALL be valid only on that local date (in the tenant's timezone) and only while its `badge_prints` row is active. A token that is tampered, expired, for another day, inactive, or for another tenant SHALL be rejected with one generic invalid-token response.

#### Scenario: Token valid on the visit day
- **WHEN** the badge is scanned on its print date while active
- **THEN** the token resolves to that visit

#### Scenario: Token used on another day
- **WHEN** the same token is scanned on a different local day
- **THEN** it is rejected as invalid

#### Scenario: Tampered token
- **WHEN** any part of the token is modified
- **THEN** it is rejected as invalid, and the response does not say why

### Requirement: Badge Prints Are Recorded Append-Only
Each print or reprint SHALL insert a `badge_prints` row (`id`, `visit_id`, `printed_by_user_id`, `printed_at`, `jti`, `active`, `reprint_reason`). Rows SHALL NOT be deleted. The only permitted update is setting `active` to `false`.

#### Scenario: First print
- **WHEN** a badge is printed for the first time
- **THEN** one active row exists with no `reprint_reason`

#### Scenario: Reprint
- **WHEN** a badge is reprinted
- **THEN** the old row is inactive, a new active row exists with a new `jti` and the reason

### Requirement: Print Endpoint Returns a PDF
`POST /api/v1/checkin/{visit_id}/badge` SHALL require `visitors:print_badge` and return `application/pdf` containing visitor name, host name, photo, visit date and the QR. It SHALL accept `Idempotency-Key`: a retry with the same key SHALL return the same PDF and SHALL NOT create a second `badge_prints` row. If an active badge already exists and no reprint is requested, the response SHALL be `409` directing the caller to reprint. Rendering SHALL run off the event loop.

#### Scenario: Successful print
- **WHEN** a gated-eligible visit is printed
- **THEN** the response is `200` with `Content-Type: application/pdf`

#### Scenario: Retry with the same Idempotency-Key
- **WHEN** the request is retried with the same key
- **THEN** the same PDF is returned and only one row exists

#### Scenario: Second print without reprint
- **WHEN** an active badge exists and the caller posts again with a new key
- **THEN** the response is `409`

#### Scenario: Another tenant's visit
- **WHEN** a caller requests a visit id belonging to another tenant
- **THEN** the response is `404`

### Requirement: Reprint Invalidates the Previous Badge
`GET /api/v1/checkin/{visit_id}/badge?reason=<text>` SHALL require `visitors:print_badge` and a `reason` of 1 to 255 characters (for example lost or damaged). It SHALL deactivate the current badge's `jti`, create a new active one, and return a new PDF. There is no cap on reprint count. The response SHALL carry `Cache-Control: no-store`. A reprint SHALL be rejected with `409` when no badge has been printed yet.

#### Scenario: Reprint after loss
- **WHEN** reception reprints with `reason=lost`
- **THEN** a new PDF is returned and scanning the old QR is rejected

#### Scenario: Reason missing
- **WHEN** `reason` is absent or blank
- **THEN** the response is a validation error and nothing is invalidated

#### Scenario: Reprint before first print
- **WHEN** no badge exists
- **THEN** the response is `409`

### Requirement: Every Print and Reprint Is Audited
Each print and reprint SHALL write an audit entry (actor, tenant, action `badge_printed` or `badge_reprinted`, visit id, `jti`, reason) via a background task, without blocking the response. The audit entry and logs SHALL NOT contain the QR token itself or ID document numbers.

#### Scenario: Print audited
- **WHEN** a badge is printed
- **THEN** an audit entry with the actor and visit id is recorded after the response

### Requirement: Checkout by Badge Scan
`POST /api/v1/checkin/badge/check-out` SHALL accept a badge QR token, resolve the visit, close it (`checked_out`), and deactivate the badge's `jti`. It SHALL be unauthenticated, with possession of a valid active same-day token as the credential, be rate-limited per IP, and be audited. A visit not currently checked in SHALL be rejected with `409`. Reception MAY instead search for the visit and use the existing checkout endpoint as the fallback.

#### Scenario: Scan closes the visit
- **WHEN** a valid active badge is scanned for a checked-in visit
- **THEN** the visit is `checked_out`, the token is inactive, and an audit entry exists

#### Scenario: Reused token after checkout
- **WHEN** the same badge is scanned again
- **THEN** it is rejected as invalid

#### Scenario: Rate limit
- **WHEN** one IP exceeds the configured limit
- **THEN** the response is `429`

### Requirement: Same-Day Re-entry by Badge Scan
When the flow is on, `POST /api/v1/checkin/badge/re-enter` SHALL let a visitor who stepped out on the visit date return by scanning an active badge for that date. It SHALL be rate-limited and audited, and it SHALL NOT work after the visit date or once the badge is deactivated.

#### Scenario: Re-entry same day
- **WHEN** an active badge is scanned on the visit date for a visit currently stepped out
- **THEN** the visit is admitted again and the entry is audited

#### Scenario: Re-entry next day
- **WHEN** the same badge is scanned the next day
- **THEN** it is rejected as invalid

### Requirement: Flow Is Tenant-Isolated and Permissioned
All badge-flow queries SHALL run on the caller's tenant-bound session. Every endpoint except the scan endpoints SHALL require `visitors:print_badge` via `require_permission`. `visitors:print_badge` SHALL be granted to Reception and Admin only.

#### Scenario: Tenant isolation
- **WHEN** a second tenant schema holds a visit with a matching name
- **THEN** search from the first tenant never returns it

#### Scenario: Role without the permission
- **WHEN** a Host user calls print
- **THEN** the response is `403`
