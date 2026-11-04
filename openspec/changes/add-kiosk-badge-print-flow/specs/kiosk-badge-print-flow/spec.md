## ADDED Requirements

### Requirement: Kiosk Endpoints Authenticate by Device Header Only
Every endpoint under `/api/v1/kiosk/checkin` SHALL require a `device-id` request header naming a registered device that is `approved`, enabled, not deleted, and has `operating_mode = kiosk`. No bearer token or login SHALL be required or accepted as a substitute. A missing header, unknown device, unapproved or disabled device, or a `security`-mode device SHALL all return the same `403` response so the reason is not revealed.

#### Scenario: Approved kiosk calls an endpoint
- **WHEN** a request carries the `device-id` of an approved, enabled kiosk and no `Authorization` header
- **THEN** the request is authorised

#### Scenario: Missing header
- **WHEN** a request has no `device-id` header
- **THEN** the response is `403` with the generic device-not-authorized message

#### Scenario: Unusable device
- **WHEN** the device is unknown, pending, disabled, deleted, or in `security` mode
- **THEN** the response is `403` with the same message in every case, and a `WARNING` is logged without the visitor data

### Requirement: Kiosk Flow Is Gated by the Badge Print Flow Flags
Kiosk endpoints SHALL respond `404` when `settings.badge_print_flow_enabled` is `false` or the tenant's `badge_print_flow_enabled` is `false`, exactly as the staff flow does.

#### Scenario: Flow off
- **WHEN** either flag is off and an approved kiosk calls any kiosk endpoint
- **THEN** the response is `404`

### Requirement: Kiosk Scope Comes From the Device
A kiosk SHALL only read or change visits whose `branch_id` equals the device's registered branch and whose visit date is today in the tenant timezone. When tenant location enforcement is on, the device's building SHALL also match the visit's. A visit outside that scope SHALL return `404`, not `403`.

#### Scenario: Visit in another branch
- **WHEN** a kiosk in branch A requests an operation on a visit in branch B
- **THEN** the response is `404`

#### Scenario: Building mismatch with enforcement on
- **WHEN** enforcement is on and the device's building differs from the visit's
- **THEN** the request is rejected and no state changes

### Requirement: Kiosk Search Is Exact-Match and Minimal
`GET /api/v1/kiosk/checkin/search?q=` SHALL match only an exact `trackingId` or exact numeric check-in code. It SHALL NOT match names or partial phone numbers. It SHALL return at most one visit as a `KioskVisitOut` containing no phone, email, ID document URL or host contact, and SHALL return `404` when nothing matches. The query text SHALL NOT be logged in full.

#### Scenario: Exact code match
- **WHEN** a kiosk searches a valid `trackingId` for a visit in its branch today
- **THEN** one `KioskVisitOut` is returned including whether photo, ID and an active badge exist and what the print gate still needs

#### Scenario: Name search is not supported
- **WHEN** a kiosk searches by a visitor's name or part of a phone number
- **THEN** the response is `404`

#### Scenario: Contact data not exposed
- **WHEN** a visit is returned
- **THEN** the body contains no phone, email or ID document URL

### Requirement: Kiosk Confirms ID, Captures Photo and Prints a Badge
The kiosk endpoints `POST /kiosk/checkin/{visit_id}/verify-id`, `POST /kiosk/checkin/{visit_id}/photo` and `POST /kiosk/checkin/{visit_id}/badge` SHALL apply the same rules as their staff counterparts: ID confirmation is idempotent; photo is JPEG/PNG only, size-limited, content-validated and never replaced (`409 photo_already_captured`); the first print requires an `approved` or `checked_in` visit with a photo and verified ID (`409` listing every unmet condition) and accepts `Idempotency-Key`; a second print while a badge is active returns `409`. The ID confirmation SHALL be recorded against the device (`id_verified_by_device_id`) rather than a user.

#### Scenario: Print succeeds
- **WHEN** the visit has a photo and verified ID and the kiosk posts to the badge endpoint
- **THEN** badge card data is returned and one active `badge_prints` row exists with `printed_by_device_id` set and `printed_by_user_id` null

#### Scenario: Gate not met
- **WHEN** the photo is missing and the ID is unverified
- **THEN** the response is `409` listing both unmet conditions

#### Scenario: Retried print
- **WHEN** the same `Idempotency-Key` is sent twice
- **THEN** the same card is returned and only one `badge_prints` row exists

#### Scenario: Oversized or non-image photo
- **WHEN** the file is over the limit or not a JPEG/PNG
- **THEN** the response is `422` and the visit is unchanged

### Requirement: Kiosk Reprint Requires a Reason and Revokes the Old Badge
`GET /kiosk/checkin/{visit_id}/badge?reason=` SHALL require a non-blank `reason`, deactivate the previous badge token, issue a new one in one transaction, return `Cache-Control: no-store`, and return `409` if no badge was ever printed.

#### Scenario: Reprint
- **WHEN** a kiosk reprints with `reason=lost`
- **THEN** the old token no longer works for scan endpoints, a new active row exists, and the reason is stored

#### Scenario: Blank reason
- **WHEN** the reason is empty or whitespace
- **THEN** the response is a validation error and nothing changes

### Requirement: Kiosk Actions Are Traced and Rate-Limited
Every kiosk verify, photo, print and reprint SHALL write an audit entry with no user actor and the device's `device_id`, using background tasks, and SHALL NOT log tokens, ID numbers or full query text. All kiosk endpoints SHALL be rate-limited with `KIOSK_BADGE_RATE_LIMIT`, returning `429` when exceeded.

#### Scenario: Audit entry
- **WHEN** a kiosk prints a badge
- **THEN** an audit entry `kiosk_badge_printed` exists referencing the device and visit

#### Scenario: Rate limit
- **WHEN** a client exceeds the limit
- **THEN** the response is `429` and a `WARNING` is logged

### Requirement: Staff Badge Endpoints Are Unchanged
The existing `/api/v1/checkin/*` staff endpoints SHALL keep requiring a bearer token and `visitors:print_badge`, with unchanged requests and responses.

#### Scenario: Staff call without a token
- **WHEN** a request to a staff `/checkin/*` endpoint carries only a `device-id` header
- **THEN** it is rejected with `401` as before
