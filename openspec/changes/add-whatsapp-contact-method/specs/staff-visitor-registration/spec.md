## MODIFIED Requirements

### Requirement: Primary contact details are required before proceeding
The system SHALL require full name, email address, phone number, and a visitor category for the primary contact, and SHALL require a preferred contact method (email, SMS, or WhatsApp) and an ID proof type, before the Visitor Info step can be completed. When the preferred contact method is WhatsApp or SMS, the phone number SHALL be a valid Indian mobile number (+91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, or 10 digits starting 6–9).

#### Scenario: Missing a required primary contact field blocks progression
- **WHEN** the staff member attempts to proceed without full name, email, phone, visitor category, preferred contact method, or ID proof type filled in for the primary contact
- **THEN** the system blocks progression and indicates which fields are missing

#### Scenario: WhatsApp is offered and requires a phone number
- **WHEN** the staff member selects WhatsApp as the preferred contact method
- **THEN** the phone field is shown as required, and progression is blocked if it is empty

#### Scenario: Non-Indian number is flagged for WhatsApp and SMS
- **WHEN** the staff member selects WhatsApp or SMS and enters a phone number that is not a valid Indian mobile number
- **THEN** the system blocks progression and indicates the number must be a valid Indian mobile number

#### Scenario: Looked-up visitor with WhatsApp preference
- **WHEN** a returning-visitor lookup returns preferred contact method `whatsapp`
- **THEN** the primary contact's preferred contact method is pre-selected as WhatsApp
