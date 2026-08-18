## Purpose

Baseline requirements for the `invitations` capability covering two gaps
found by direct investigation rather than assumption: the creation payload's
required/optional fields are undocumented for any OpenAPI-reading tool, and
the confirmation-email/QR dispatch path had no test proving it actually
produces a deliverable email with a valid QR attachment.

## ADDED Requirements

### Requirement: Invitation Creation's Mandatory Fields Are Documented and Test-Verified
The system SHALL document, in `POST /invitations`'s `payload` field
description, which fields of each nested object (primary contact, each
visitor, visit details, carried items, each vehicle, consents) are mandatory
versus optional, derived from each schema's own required-field list rather
than duplicated by hand, and SHALL reject a request missing any top-level
mandatory field or containing an invalid enum value with a 422.

#### Scenario: Missing a required top-level field is rejected
- **WHEN** a creation request omits `registrationType`, `primaryContact`,
  `visitDetails`, or `consents` entirely
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Invalid enum value is rejected
- **WHEN** a creation request supplies a value for `idProofType`,
  `vehicleType`, or a carried-item category that is not one of the
  supported enum values
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: A vehicle or visitor missing its own required field is rejected
- **WHEN** an entry in `vehicles` omits `licensePlate`, or an entry in
  `visitors` omits `fullName`
- **THEN** the system rejects the request with a 422 validation error

#### Scenario: Documented required fields match the schema
- **WHEN** the `payload` field's description is compared against each
  nested Pydantic schema's own `model_json_schema()["required"]` list
- **THEN** every field the description calls mandatory is actually required
  by its schema, and vice versa

### Requirement: Visit-Confirmation Dispatch Is Verified Against a Real Mail Catcher
The system SHALL be provably capable of delivering the visit-confirmation
notification — including a valid QR-code image attachment — through actual
SMTP to a reachable mail catcher, not only asserted against a fake/recording
sender.

#### Scenario: Confirmation email arrives with a valid QR attachment
- **WHEN** `send_visit_confirmation` runs for a submitted invitation using
  the real SMTP-backed sender
- **THEN** a message addressed to the invitation's primary contact, with the
  expected subject, and carrying a valid PNG attachment is observable
  through the mail catcher's own API
