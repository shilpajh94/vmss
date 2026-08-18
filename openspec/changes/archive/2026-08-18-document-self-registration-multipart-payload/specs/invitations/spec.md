## Purpose

Baseline requirement for the `invitations` capability covering Swagger/
OpenAPI discoverability of the self-registration endpoint's multipart
`payload` field — a gap surfaced when the user tested API-10 against
`/docs` and could not tell the JSON shape the endpoint expected. This delta
adds one requirement to the same not-yet-baselined `invitations` capability
that `harden-invitation-tracking-fidelity` (pending) is also establishing;
the two merge into one baseline spec when both are synced.

## ADDED Requirements

### Requirement: Self-Registration's Multipart Payload Is Self-Documenting in Swagger
The system SHALL expose, in the generated OpenAPI schema for
`POST /invitations/{tracking_token}/register`, a named example of the
`payload` form field's JSON shape for each supported `registrationType`
(`individual` and `group`), so a caller using Swagger UI's "Try it out" can
discover and populate the correct request without reading source code.

#### Scenario: OpenAPI schema carries both registration-type examples
- **WHEN** the application's OpenAPI schema is generated
- **THEN** the self-registration route's `multipart/form-data` request body
  includes an `individual` example and a `group` example, and each
  example's `payload` value parses as valid JSON matching
  `SelfRegistrationSubmit`

#### Scenario: File-upload parameters state their purpose
- **WHEN** the OpenAPI schema for the self-registration route is inspected
- **THEN** `primaryContactIdProofFile` and `visitorIdProofFiles` each carry a
  description identifying them as ID-proof image/PDF uploads, with the
  visitor-list one documented as order-matched to `payload.visitors`
