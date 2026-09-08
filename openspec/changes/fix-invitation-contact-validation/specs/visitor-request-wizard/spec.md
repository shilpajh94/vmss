## MODIFIED Requirements

### Requirement: Visitor Info step requires core contact and address details
The system SHALL require full name, address, visitor category, and ID proof type before the Visitor Info step can be completed, for the individual visitor or for the primary contact and every added group visitor. The system SHALL require at least one of email or phone number for each visitor, but SHALL NOT require both. For the individual visitor or primary contact specifically, the system SHALL require the contact field matching the selected preferred contact method — email address when "email" is selected, phone number when "SMS" is selected.

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

### Requirement: ID proof and profile image can optionally be uploaded as supporting documents
The system SHALL let the visitor attach an image or PDF as ID proof, and separately an image as a profile photo, for themselves (individual) or for any visitor in the list (group). The system SHALL reject files that are not PNG, JPG, or PDF, or that exceed 5MB, for either upload. The system SHALL NOT require a profile image before the Visitor Info step can be completed. When a profile image is supplied, the system SHALL include it in the submitted registration request.

#### Scenario: Valid ID document is accepted
- **WHEN** the visitor selects a PNG, JPG, or PDF file under 5MB as ID proof
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Valid profile image is accepted
- **WHEN** the visitor selects a PNG or JPG file under 5MB as a profile image and submits the registration
- **THEN** the system accepts the file and includes it in the submitted request

#### Scenario: Registration proceeds without a profile image
- **WHEN** the visitor completes the Visitor Info step without attaching a profile image for themselves or any group visitor
- **THEN** the system allows progression past the Visitor Info step

#### Scenario: Oversized or unsupported file is rejected
- **WHEN** the visitor selects a file over 5MB or with an unsupported type for either ID proof or profile image
- **THEN** the system rejects the file and explains why, without associating it with the visitor's entry
