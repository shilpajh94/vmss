## Purpose

Baseline requirement for the `invitations` capability covering Swagger/
OpenAPI discoverability of `POST /invitations`'s multipart `payload` field on
the rendering surface this project actually exposes (`/docs`), not only on
the raw generated schema document.

## ADDED Requirements

### Requirement: Invitation Creation's Multipart Payload Is Self-Documenting Without "Try It Out"
The system SHALL make the full JSON shape of `POST /invitations`'s `payload`
form field — for both the `individual` and `group` registration types —
readable directly from the field's own OpenAPI parameter description, so a
caller reading Swagger's Parameters table (before opening "Try it out" and
regardless of whether the rendering surface applies operation-level
multipart examples) can discover and construct a correct request.

#### Scenario: Payload description carries both registration-type examples
- **WHEN** the application's OpenAPI schema is generated
- **THEN** the `payload` parameter's description for `POST /invitations`
  contains an `individual` example and a `group` example, and each embedded
  example parses as valid JSON matching `InvitationCreate`

#### Scenario: File-upload parameters state their purpose and ordering
- **WHEN** the OpenAPI schema for `POST /invitations` is inspected
- **THEN** `primaryContactIdProofFile` and `visitorIdProofFiles` each carry a
  description identifying them as ID-proof image/PDF uploads, with the
  visitor-list one documented as order-matched to `payload.visitors`
