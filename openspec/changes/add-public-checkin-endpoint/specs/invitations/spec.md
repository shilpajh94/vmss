## ADDED Requirements

### Requirement: An Approved Invitation Can Be Publicly Checked In By Tracking ID
Any caller SHALL be able to transition an `approved` invitation to
`checked_in` by presenting its `tracking_id` (`INV-XXXXXXXX`) at a public,
unauthenticated endpoint — no bearer token or `invitations:checkin`
permission required — subject to a rate limit keyed by caller IP, mirroring
`GET /invitations/track`'s existing throttling. Checking in an invitation
that is not currently `approved` SHALL be rejected with 409. Checking in an
invitation whose `watchlistFlagged` is `true` and has not been cleared via
`POST /invitations/{id}/watchlist-override` SHALL be rejected with 409, same
as the staff check-in path. An unknown `tracking_id` SHALL be rejected with
404. The endpoint SHALL accept an `Idempotency-Key` header
(api-conventions.md §3): a retried request with the same key and tenant
context SHALL return the original response rather than re-performing the
transition. Because there is no authenticated caller, the recorded audit
entry SHALL have no human actor rather than omitting the audit trail
entirely.

#### Scenario: Public check-in transitions status with no credential required
- **WHEN** a caller presents the `tracking_id` of an `approved`, non-flagged
  invitation to the public check-in endpoint, with no `Authorization` header
- **THEN** the invitation's status becomes `checked_in`, a check-in timestamp
  is recorded, and the audit entry for the action records no human actor

#### Scenario: Checking in a non-approved invitation is rejected
- **WHEN** a caller presents the `tracking_id` of an invitation whose status
  is not `approved` (e.g. `submitted`, already `checked_in`, or `denied`)
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: Watchlist-flagged invitation blocks public check-in
- **WHEN** a caller presents the `tracking_id` of an `approved` invitation
  whose `watchlistFlagged` is `true` and has not been cleared via
  `POST /invitations/{id}/watchlist-override`
- **THEN** the request is rejected with 409 and the invitation is unchanged

#### Scenario: Unknown tracking ID is rejected
- **WHEN** a caller presents a `tracking_id` that does not exist
- **THEN** the request is rejected with 404

#### Scenario: Retried public check-in with the same idempotency key is not duplicated
- **WHEN** a caller retries the public check-in endpoint with the same
  `Idempotency-Key` header and the same `tracking_id`
- **THEN** the invitation is checked in exactly once, and both requests
  receive the same response body

#### Scenario: Repeated public check-in attempts are throttled
- **WHEN** a caller exceeds the configured rate limit for the public
  check-in endpoint
- **THEN** the system rejects further requests with the standard error
  envelope until the limit window resets

### Requirement: The Staff Check-In Endpoint Is Deprecated In Favor Of Public Check-In By Tracking ID
`PATCH /api/v1/invitations/{id}/check-in` (bearer token, `invitations:checkin`
permission, UUID `id`) SHALL continue to function exactly as before during a
migration window — same transitions, same 409/403/404 rules, same
`Idempotency-Key` support — but SHALL additionally return a `Deprecation`
response header, and its target removal date SHALL be documented, per
api-conventions.md §2. It SHALL NOT be removed as part of introducing the
public tracking-ID check-in endpoint.

#### Scenario: Deprecated staff check-in still functions and signals deprecation
- **WHEN** a caller with `invitations:checkin` at the invitation's branch
  calls `PATCH /api/v1/invitations/{id}/check-in` on an `approved`,
  non-flagged invitation
- **THEN** the invitation is checked in exactly as before, and the response
  includes a `Deprecation` header
