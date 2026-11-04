## ADDED Requirements

### Requirement: Per-Tenant Toggle
The system SHALL gate all zone access routes behind the tenant's `zone_access_enabled` setting, default `false`, switched with `PATCH /tenants/me/settings` and reported by `GET /tenants/me`. There is no environment variable.

#### Scenario: Toggle off
- **WHEN** the tenant's toggle is off and any zone, mapping, scan or zone-inside route is called with valid credentials
- **THEN** the response is 404 and no data is read or written

#### Scenario: Toggle off leaves existing flows unchanged
- **WHEN** the toggle is off
- **THEN** badge check-in, check-out, re-enter and the dashboard behave exactly as before

#### Scenario: Turning it on
- **WHEN** a caller with `tenants:update` sends `{"zoneAccessEnabled": true}` to `PATCH /tenants/me/settings`
- **THEN** the toggle is stored, the change is audited, other switches are untouched, and zone routes stop returning 404

#### Scenario: Permission is still 403
- **WHEN** the toggle is on and a caller lacks the route's permission
- **THEN** the response is 403, never 404

### Requirement: Zone Management
The system SHALL let holders of `zones:manage` create, read, update and soft-delete zones tied to a branch and optionally a building and floor, and link zones to security gates of the same branch.

#### Scenario: Create zone
- **WHEN** a caller with `zones:manage` creates a zone with a unique code at a branch
- **THEN** the zone is stored and returned in the standard envelope

#### Scenario: Duplicate code
- **WHEN** a zone with the same code already exists, undeleted, at that branch
- **THEN** the response is 409; a soft-deleted zone's code is reusable

#### Scenario: Cross-branch link rejected
- **WHEN** a zone is linked to a building, floor or gate device belonging to a different branch, or to a device that is deleted or not in security mode
- **THEN** the response is 422

#### Scenario: Soft delete
- **WHEN** a zone is deleted
- **THEN** `deleted_at` is set, the row remains for history, and the zone is denied for entry with reason `zone_inactive`

#### Scenario: Permission denied
- **WHEN** a caller without `zones:manage` calls a write route
- **THEN** the response is 403

### Requirement: Allowed Zones Mapping
The system SHALL let reception map allowed zones per invitation at registration or invitation time, and administrators map default zones per visitor category. A per-invitation mapping replaces the category default.

#### Scenario: Invitation mapping wins
- **WHEN** an invitation has its own allowed zones and its category has different defaults
- **THEN** only the invitation's zones are allowed

#### Scenario: Category default
- **WHEN** an invitation has no zone mapping
- **THEN** the visitor category's default zones are allowed

#### Scenario: No mapping
- **WHEN** neither exists
- **THEN** every zone is denied with reason `zone_not_allowed`

#### Scenario: Zone from another branch
- **WHEN** a mapped zone is not in the invitation's branch
- **THEN** the response is 422

### Requirement: Entry Decision
The system SHALL decide entry with `can_enter(visit, zone)` returning allow or deny with one reason, evaluating in this order: `zone_inactive`, `gate_not_linked`, `not_checked_in`, `not_approved`, `blacklisted`, `outside_time_window`, `zone_not_allowed`.

#### Scenario: All conditions met
- **WHEN** the visit is checked in, approved, not flagged (or flag overridden), within its time window, and the zone is allowed and linked to the gate
- **THEN** the decision is allow with no reason

#### Scenario: First failing check wins
- **WHEN** a visit fails several checks
- **THEN** the reason is the earliest failing check in the stated order

#### Scenario: Watchlist override
- **WHEN** the visit is `watchlist_flagged` with an override recorded
- **THEN** `blacklisted` is not raised

### Requirement: Gate Scan
The system SHALL expose `POST /api/v1/access/scan` accepting a badge QR token, gate, zone and direction, requiring `access:scan`, rate limited, and recording every scan in an append-only log.

#### Scenario: Allowed entry
- **WHEN** a valid, active, same-day badge is scanned for an allowed zone
- **THEN** the response is `allowed: true` and an `entry` event is logged

#### Scenario: Invalid or foreign token
- **WHEN** the token is tampered, expired, inactive, from another tenant or another day
- **THEN** one generic invalid-token `400` response is returned and nothing reveals which check failed

#### Scenario: Exit never denied
- **WHEN** direction is `exit`
- **THEN** it is allowed and logged, even with no prior entry or after the badge's zone is deleted

#### Scenario: Gate is a security device
- **WHEN** `gateId` is not a live security-mode device
- **THEN** the response is 404 and nothing is logged

#### Scenario: Rate limit
- **WHEN** a client exceeds the scan rate limit
- **THEN** the response is 429 in the standard error envelope and a WARNING is logged

#### Scenario: Retried scan
- **WHEN** the same `Idempotency-Key` is sent twice
- **THEN** one event is logged and the first response is returned

#### Scenario: Permission denied
- **WHEN** the caller lacks `access:scan`
- **THEN** the response is 403

#### Scenario: Tenant isolation
- **WHEN** a tenant B user scans a tenant A badge
- **THEN** the token is rejected and tenant A data is unreachable

### Requirement: Denied Entry Handling
The system SHALL, on every denied entry, log at WARNING, write an audit entry, and alert Security at the visit's branch, without exposing identity documents, tokens or the visitor's contact details.

#### Scenario: Denial side effects
- **WHEN** an entry is denied
- **THEN** a `zone_entry_denied` WARNING carries tenant, user, visit, zone, gate and reason; an audit row `zone_entry_denied` is written off the request path; a push to Security at that branch is enqueued

#### Scenario: Alert deduplication
- **WHEN** the same visit is denied for the same zone and reason repeatedly within the dedupe window
- **THEN** one alert is sent, but every denial is still logged and audited

#### Scenario: No Security holders
- **WHEN** no user holds the Security role at the branch
- **THEN** the denial still succeeds and a WARNING notes the missing recipient

### Requirement: Front-Desk Check-In Is a Zone Entry
When the tenant's toggle is on, a QR or code check-in made from a security device linked to exactly one live zone SHALL be judged by the entry decision and logged as an entry at that zone.

#### Scenario: Allowed
- **WHEN** such a check-in is for a visit allowed in that zone
- **THEN** the visit is checked in and one allowed `entry` event is recorded with the device as gate

#### Scenario: Denied blocks the check-in
- **WHEN** the visit is not allowed in that zone
- **THEN** the response is 403, the visit is not checked in, a denied event and audit row are recorded, and Security is alerted

#### Scenario: Device not tied to one zone
- **WHEN** the check-in has no device, a non-security device, or a device linked to zero or several zones
- **THEN** it behaves as before and nothing is logged

#### Scenario: Toggle off or repeat scan
- **WHEN** the toggle is off, or the visit is already checked in
- **THEN** nothing zone-related happens and no second event is logged

