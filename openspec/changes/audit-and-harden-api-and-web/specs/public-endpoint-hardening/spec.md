## Purpose

Lets the API close unauthenticated access that exposes staff PII or changes
visit state, without breaking the web, Flutter or kiosk clients that rely on
it today. Each endpoint keeps its legacy public behaviour, flagged with a
`Deprecation` header, until an operator turns on strict enforcement.

## ADDED Requirements

### Requirement: Hardening Mode Is an Explicit, Default-Off Setting
The system SHALL expose one deployment setting, `PUBLIC_ENDPOINT_HARDENING`.
It defaults to off. While it is off, every endpoint covered by this
capability SHALL accept the same unauthenticated requests it accepts today
and return the same response body. While it is on, each covered endpoint
SHALL apply the strict behaviour its requirement below describes. The
setting SHALL be documented in the example environment file.

#### Scenario: Default deployment keeps today's public behaviour
- **WHEN** `PUBLIC_ENDPOINT_HARDENING` is unset, and an unauthenticated
  client calls any endpoint covered by this capability with a request that
  succeeds today
- **THEN** the request succeeds with the same status code and the same
  response body fields as before this change

#### Scenario: Strict mode is opt-in
- **WHEN** an operator sets `PUBLIC_ENDPOINT_HARDENING=true`
- **THEN** every endpoint covered by this capability applies its strict
  behaviour, with no other configuration change needed

### Requirement: Legacy Unauthenticated Access Is Signalled as Deprecated
While hardening mode is off, a covered endpoint that serves a request
without the credential strict mode would require SHALL include a
`Deprecation: true` response header and a `Link` header pointing at the
feature documentation that names the replacement. Requests that already
carry the credential SHALL NOT receive the header.

#### Scenario: Unauthenticated employee listing is flagged
- **WHEN** a client calls `GET /auth/employees` with no bearer token while
  hardening mode is off
- **THEN** the response succeeds as today and carries a `Deprecation: true`
  header

#### Scenario: Authenticated call is not flagged
- **WHEN** a caller holding `employees:view` calls `GET /auth/employees`
  with a valid bearer token
- **THEN** the response carries no `Deprecation` header

### Requirement: Employee Listing and Host Search Withhold Contact PII From Anonymous Callers in Strict Mode
With hardening mode on, `GET /auth/employees` called without a valid bearer
token holding `employees:view` SHALL omit each employee's email, phone,
employee code and branch roles, and return only the fields a public host
picker needs (id, full name, department, avatar URL). With hardening mode
on, `GET /hosts/search` called without an approved device key or a valid
bearer token SHALL omit each result's email. Authenticated callers holding
the permission SHALL get the full response in either mode.

#### Scenario: Anonymous employee list in strict mode
- **WHEN** hardening mode is on and a client calls `GET /auth/employees`
  with no bearer token
- **THEN** each returned employee has no email, phone, employee code or
  branch-role data

#### Scenario: Permitted caller in strict mode
- **WHEN** hardening mode is on and a caller holding `employees:view` calls
  `GET /auth/employees`
- **THEN** every employee field is returned exactly as today

#### Scenario: Anonymous host search in strict mode
- **WHEN** hardening mode is on and a client calls `GET /hosts/search` with
  neither a device key nor a bearer token
- **THEN** no result carries an email

### Requirement: Tracking-ID Check-In Requires a Trusted Caller in Strict Mode
With hardening mode on, `PATCH /api/v2/invitations/{trackingId}/check-in`
SHALL require either an `X-Device-Key` that resolves to an approved device,
or a bearer token holding `invitations:checkin` at the invitation's branch.
A request with neither SHALL be rejected with 401 before any state change,
and SHALL disclose nothing about the invitation.

#### Scenario: Anonymous remote check-in is refused in strict mode
- **WHEN** hardening mode is on and a client with no device key and no
  bearer token calls the tracking-ID check-in for an approved invitation
- **THEN** the response is 401, the invitation stays `approved`, and the
  body contains no visitor data

#### Scenario: Approved kiosk device still checks in
- **WHEN** hardening mode is on and an approved device's key accompanies
  the tracking-ID check-in for an approved invitation
- **THEN** the check-in succeeds exactly as it does today

### Requirement: Email Tracking Lookup Requires Proof of Email Ownership in Strict Mode
With hardening mode on, `GET /invitations/track?email=` SHALL require a valid
OTP proof token for that same email address (issued by the identity
verification flow). A request without one SHALL be rejected with 401. In
either mode, the response SHALL remain limited to each match's tracking ID
and status.

#### Scenario: Email lookup without proof in strict mode
- **WHEN** hardening mode is on and a client calls the email tracking
  lookup with no proof token
- **THEN** the response is 401 and lists no tracking IDs

#### Scenario: Email lookup with a matching proof token
- **WHEN** hardening mode is on and a client presents a valid proof token
  issued for the same email
- **THEN** the response lists that email's tracking IDs and statuses

### Requirement: Kiosk Reads Require Authentication in Strict Mode
With hardening mode on, `GET /kiosks` and `GET /kiosks/{id}` SHALL require a
bearer token holding `kiosks:view`, matching the kiosks capability's stated
contract. With hardening mode off, an unauthenticated caller SHALL NOT be
able to list hidden kiosks: `includeHidden=true` without `kiosks:view`
SHALL be treated as `false`.

#### Scenario: Anonymous kiosk listing in strict mode
- **WHEN** hardening mode is on and a client calls `GET /kiosks` with no
  bearer token
- **THEN** the response is 401

#### Scenario: Anonymous caller cannot reveal hidden kiosks
- **WHEN** hardening mode is off and a client calls
  `GET /kiosks?includeHidden=true` with no bearer token
- **THEN** only non-hidden kiosks are returned
