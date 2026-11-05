## MODIFIED Requirements

### Requirement: Print Gate
A badge SHALL be printed only when the visit is `approved` or `checked_in`, a photo has been captured, and, unless the tenant has turned `badge_print_requires_id_verification` off, the ID is verified. Otherwise the request SHALL be rejected with `409` naming every unmet condition. The rule SHALL be identical for first print, reprint, reception and kiosk.

#### Scenario: Print succeeds when all conditions are met
- **WHEN** the visit is approved, has a photo and a verified ID
- **THEN** the badge is printed

#### Scenario: Unverified ID blocks print by default
- **WHEN** the tenant requires ID verification and the visit has no verified ID
- **THEN** the response is `409` listing `id_not_verified` (and `photo_missing` if applicable)

#### Scenario: Unverified ID does not block print when skipped
- **WHEN** the tenant has `badge_print_requires_id_verification` set to `false`, and the visit is approved with a photo but no verified ID
- **THEN** the badge is printed and no `id_not_verified` condition is reported

#### Scenario: Photo is still required when ID verification is skipped
- **WHEN** the tenant has skipped ID verification and the visit has no photo
- **THEN** the response is `409` listing `photo_missing`

## ADDED Requirements

### Requirement: Admin Toggles ID Verification for Badge Print
`PATCH /api/v1/tenants/me/settings` SHALL accept `badgePrintRequiresIdVerification` (boolean, default `true`), require `tenants:update`, change only the switches present in the body, and be audited. `TenantOut` SHALL expose it. The tenant SHALL come from the token, never the body.

#### Scenario: Admin turns the requirement off
- **WHEN** an admin sends `{"badgePrintRequiresIdVerification": false}`
- **THEN** the tenant setting is `false` and an audit entry is written

#### Scenario: Caller without permission
- **WHEN** a user lacking `tenants:update` sends the request
- **THEN** the response is `403`

### Requirement: Check-In Requires Verified ID When Print Skips It
When the badge print flow is enabled and the tenant has `badge_print_requires_id_verification` set to `false`, every check-in path (badge scan, re-entry, desk and tracking-ID check-in) SHALL be rejected with `409` and an `ID not verified` detail unless the visit has `id_verified_at`. An already-checked-in visit SHALL keep its idempotent no-op behaviour. Check-out SHALL never be blocked by this rule. For tenants that require verification at print, check-in behaviour SHALL be unchanged.

#### Scenario: Unverified visit cannot check in
- **WHEN** a badge was printed without ID verification and its QR is scanned for check-in
- **THEN** the response is `409` stating the ID is not verified and the visit stays not checked in

#### Scenario: Verification then check-in
- **WHEN** reception calls verify-id for that visit and the badge is scanned again
- **THEN** the check-in succeeds

#### Scenario: Default tenant unaffected
- **WHEN** a tenant requires ID verification at print and a visit is checked in
- **THEN** no additional ID check is made at check-in

#### Scenario: Check-out is not blocked
- **WHEN** a checked-in visit is checked out
- **THEN** the check-out succeeds regardless of the setting
