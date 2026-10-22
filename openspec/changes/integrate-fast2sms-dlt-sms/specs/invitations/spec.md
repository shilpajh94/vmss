## ADDED Requirements

### Requirement: `whatsapp` is an accepted preferred contact method
The `preferredContactMethod` of a primary contact SHALL accept `whatsapp` in addition to `email` and `sms`. WHEN it is `whatsapp`, a phone number SHALL be required (same rule as `sms`), and the existing default of `email` SHALL be unchanged. Read responses that expose the method SHALL return `whatsapp` for such invitations. This is an additive widening of an existing field and ships within `v1`.

#### Scenario: Create with WhatsApp preference and a phone
- **WHEN** a registration is submitted with `preferredContactMethod: "whatsapp"` and a valid `phone`
- **THEN** it is accepted and stored with that method

#### Scenario: WhatsApp preference without a phone
- **WHEN** a registration is submitted with `preferredContactMethod: "whatsapp"` and no `phone`
- **THEN** it is rejected with a validation error stating that phone is required

#### Scenario: Existing values unaffected
- **WHEN** a registration is submitted with `email` or `sms`, or omits the method
- **THEN** behaviour is unchanged
