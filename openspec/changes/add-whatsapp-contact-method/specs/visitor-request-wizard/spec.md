## ADDED Requirements

### Requirement: Preferred contact method offers Email, SMS, and WhatsApp
The system SHALL let the visitor choose a preferred contact method of Email, SMS, or WhatsApp for the primary contact, defaulting to Email, and SHALL submit the selected value as the request's preferred contact method.

#### Scenario: WhatsApp is selectable
- **WHEN** the visitor views the Preferred Contact Method selector on the Visitor Info step
- **THEN** Email, SMS, and WhatsApp are offered, with Email selected by default

#### Scenario: WhatsApp requires a phone number
- **WHEN** the visitor selects WhatsApp and attempts to proceed without a phone number
- **THEN** the system blocks progression, marks the phone field as required, and indicates a phone number is needed

#### Scenario: Non-Indian number is flagged for WhatsApp and SMS
- **WHEN** the visitor selects WhatsApp or SMS and enters a phone number that is not a valid Indian mobile number (+91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, or 10 digits starting 6–9)
- **THEN** the system blocks progression and indicates the number must be a valid Indian mobile number

#### Scenario: Email and SMS behave as before
- **WHEN** the visitor selects Email or SMS
- **THEN** the required-field rules for Email (email address) and SMS (phone number) are unchanged apart from the Indian-number check above

### Requirement: WhatsApp contact method is preserved and displayed
The system SHALL display "WhatsApp" for a preferred contact method of `whatsapp` wherever the contact method is shown, and SHALL retain it when pre-filling the wizard from a returning visitor's profile.

#### Scenario: Review step shows WhatsApp
- **WHEN** the visitor reaches the review step with WhatsApp selected
- **THEN** the Preferred Contact Method row reads "WhatsApp"

#### Scenario: Prefill keeps WhatsApp
- **WHEN** a returning visitor's prefill profile has preferred contact method `whatsapp`
- **THEN** the wizard's Preferred Contact Method is pre-selected as WhatsApp rather than falling back to the default

#### Scenario: Unknown value does not break display
- **WHEN** a response carries a preferred contact method outside email, sms, and whatsapp
- **THEN** the screen still renders, falling back to the default selection or omitting the label
