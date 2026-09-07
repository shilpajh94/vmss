## MODIFIED Requirements

### Requirement: Visitor Info step requires core contact and address details
The system SHALL require full name, address, visitor category, and ID proof type before the Visitor Info step can be completed, for the individual visitor or for the primary contact and every added group visitor. The system SHALL require at least one of email or phone number for each visitor, but SHALL NOT require both. For the individual visitor or primary contact specifically, the system SHALL require the contact field matching the selected preferred contact method — email address when "email" is selected, phone number when "SMS" is selected — and SHALL default the preferred contact method to "Email" at the start of a new session, so this requirement never blocks progression before the visitor has interacted with the preferred-contact-method control. Any validation error raised against the preferred contact method itself SHALL be visibly displayed, never silently blocking progression with no indication of why.

#### Scenario: Missing a required contact field blocks progression
- **WHEN** the visitor attempts to proceed without full name, address, visitor category, or ID proof type filled in
- **THEN** the system blocks progression and indicates which fields are missing

#### Scenario: Missing both email and phone blocks progression
- **WHEN** the visitor attempts to proceed with neither email nor phone filled in, for themselves or for any added group visitor
- **THEN** the system blocks progression and indicates that a reachable contact is required

#### Scenario: Missing the contact field for the selected preferred contact method blocks progression
- **WHEN** the individual visitor or primary contact selects "Email" as the preferred contact method but leaves email address blank, or selects "SMS" but leaves phone number blank
- **THEN** the system blocks progression and indicates the missing contact field

#### Scenario: Phone-only visitor with SMS preferred is accepted
- **WHEN** the individual visitor or primary contact selects "SMS" as the preferred contact method, fills in phone number, and leaves email address blank
- **THEN** the system allows progression past the Visitor Info step

#### Scenario: Phone-only group visitor is accepted
- **WHEN** an added group visitor has a phone number and no email address filled in
- **THEN** the system allows progression past the Visitor Info step

#### Scenario: A brand-new session defaults to Email and does not block on an untouched preferred contact method
- **WHEN** the visitor opens the wizard for the first time, fills in every other required field including email, and never interacts with the Preferred Contact Method control
- **THEN** the preferred contact method is treated as "Email" and the system allows progression past the Visitor Info step

#### Scenario: A validation error on preferred contact method is visible
- **WHEN** the preferred contact method fails validation for any reason
- **THEN** the system displays a visible error message next to the Preferred Contact Method control, rather than blocking progression with no visible indication
