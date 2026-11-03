## Purpose

Lets reception staff search checked-in visits, verify ID, capture photos, and print or reprint visitor badges.

## ADDED Requirements

### Requirement: Badge print request sends no idempotency header
The system SHALL print a badge via `POST /checkin/{id}/badge` without an `Idempotency-Key` header or any other custom request header beyond those already used for authentication and branch scoping, and SHALL open the returned PDF for printing. This supersedes the `Idempotency-Key` behavior of the "Reception can print a badge" requirement.

#### Scenario: Print request has no Idempotency-Key
- **WHEN** reception prints a badge for an eligible visit
- **THEN** the request carries no `Idempotency-Key` header
- **AND** the browser's CORS preflight does not request `idempotency-key`

#### Scenario: Successful print
- **WHEN** the visit is approved or checked in, has a photo, and has verified ID, and reception prints
- **THEN** the PDF is opened for printing and the row shows an active badge

#### Scenario: Retry after a failure
- **WHEN** a print fails with a network error or 5xx and reception prints again
- **THEN** a fresh request is sent without any key, and a 409 active-badge response directs reception to Reprint
