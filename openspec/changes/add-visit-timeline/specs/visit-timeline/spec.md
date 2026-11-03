## ADDED Requirements

### Requirement: Timeline Event Types
The timeline SHALL expose exactly these event types: `invited`, `approved`, `denied`, `approval_reverted`, `id_verified`, `photo_captured`, `checked_in`, `checked_out`, `badge_printed`, `badge_reprinted`, `notification_sent`. Each event SHALL carry `eventType`, `occurredAt`, a short `summary`, and the acting user's display name when one exists. Zone entry/exit and overstay SHALL NOT be event types until their features exist.

#### Scenario: Known audit action maps to an event type
- **WHEN** an invitation has an `invitation_approved` audit row
- **THEN** its timeline contains one `approved` event at that row's `created_at`

#### Scenario: Unmapped audit action is excluded
- **WHEN** an invitation has an audit row whose action is not in the mapping (for example `invitation_exported`)
- **THEN** it does not appear in the timeline

#### Scenario: Check-in variants collapse
- **WHEN** a visit is checked in by QR, by code, publicly, or by reception
- **THEN** each produces a `checked_in` event

### Requirement: Merged Sources
The timeline for a visit SHALL merge `audit_logs` (entity is the invitation), `badge_prints` (by `visit_id`) and `notifications` (by `invitation_id`) into one result. Notifications sent to several recipients as one dispatch SHALL appear once, not once per recipient. Badge events SHALL come from `badge_prints` only; the matching badge audit rows SHALL NOT also produce events.

#### Scenario: Badge shown once
- **WHEN** a badge is printed
- **THEN** the timeline has one `badge_printed` event, not two

#### Scenario: Reprint
- **WHEN** a badge is reprinted
- **THEN** the timeline has a `badge_reprinted` event whose summary includes the reprint reason

#### Scenario: Fan-out notification collapsed
- **WHEN** one dispatch created notifications for three recipients
- **THEN** the timeline has one `notification_sent` event

### Requirement: No Per-Row Queries
Building one timeline page SHALL issue a constant number of queries regardless of page size: one merged, sorted, paginated query, one count, and one batched actor lookup.

#### Scenario: Query count does not grow
- **WHEN** a timeline page of 5 events and a page of 50 events are built
- **THEN** both issue the same number of SQL statements

### Requirement: Invitation Timeline Endpoint
`GET /api/v1/invitations/{invitation_id}/timeline` SHALL return the visit's events in a `PaginatedEnvelope`, requiring `timeline:view`. An invitation id that does not exist in the caller's tenant schema SHALL return `404`.

#### Scenario: Default order
- **WHEN** the endpoint is called with no sort parameters
- **THEN** events are returned newest first

#### Scenario: Unknown invitation
- **WHEN** the id matches no invitation in the caller's tenant
- **THEN** the response is `404` with the standard error envelope

### Requirement: Visitor Timeline Endpoint
`GET /api/v1/visitors/{visitor_id}/timeline` SHALL treat `visitor_id` as an `invitation_visitors.id` and return the timeline of the invitation that visitor belongs to, in the same shape and with the same rules as the invitation endpoint. An id that matches no visitor SHALL return `404`.

#### Scenario: Co-visitor resolves to its invitation
- **WHEN** the endpoint is called with a co-visitor's id
- **THEN** the response is that visitor's invitation timeline

#### Scenario: Unknown visitor
- **WHEN** the id matches no `invitation_visitors` row
- **THEN** the response is `404`

### Requirement: Pagination, Filtering and Sorting
Both endpoints SHALL accept `page` and `pageSize` (default 20, maximum 100), `occurredAfter` and `occurredBefore` (inclusive datetimes), `sortBy` limited to `occurred_at` or `event_type`, and `sortOrder` of `asc` or `desc`. Any other `sortBy` value SHALL be rejected with `422`. Ties SHALL be broken by a stable secondary key so pages never overlap or skip.

#### Scenario: Date range
- **WHEN** `occurredAfter` and `occurredBefore` are supplied
- **THEN** only events within the range are returned and `total` counts only those

#### Scenario: Sort whitelist
- **WHEN** `sortBy=jti`
- **THEN** the response is `422` and no query runs

#### Scenario: Stable paging
- **WHEN** two events share the same `occurredAt`
- **THEN** walking every page returns each event exactly once

### Requirement: PII Masking and Safe Payload
Timeline responses SHALL NOT include raw audit `diff` content, identity document numbers or images, JWTs, badge tokens, OTPs, or storage keys. Phone numbers and emails appearing in a notification summary SHALL be masked. Actor display names SHALL be the only user identity exposed.

#### Scenario: Masked contact in notification summary
- **WHEN** a notification body contains a phone number or email
- **THEN** the summary contains only the masked form

#### Scenario: Audit diff not exposed
- **WHEN** an audit row has a `diff` containing field values
- **THEN** the event carries no `diff` and none of those values

### Requirement: Permission Gate
Both endpoints SHALL require `timeline:view`. A caller without it SHALL receive `403` through the standard error envelope.

#### Scenario: Permission denied
- **WHEN** a user without `timeline:view` calls either endpoint
- **THEN** the response is `403`

### Requirement: Tenant Isolation
Timeline queries SHALL run only on the caller's tenant-bound session. A visit, visitor or event in another tenant's schema SHALL be unreachable, and an id belonging to another tenant SHALL return `404`.

#### Scenario: Cross-tenant id
- **WHEN** tenant A's user requests the timeline of an invitation that exists only in tenant B's schema
- **THEN** the response is `404`

### Requirement: Documentation
`docs/features/timeline.md` SHALL describe the event types and their sources, both endpoints, query parameters, the permission, and masking rules.

#### Scenario: Docs present
- **WHEN** the change is complete
- **THEN** `docs/features/timeline.md` exists and lists every event type in this spec
