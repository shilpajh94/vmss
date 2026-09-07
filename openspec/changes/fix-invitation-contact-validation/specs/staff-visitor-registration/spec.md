## MODIFIED Requirements

### Requirement: Primary contact details are required before proceeding
The system SHALL require full name, a visitor category, a preferred contact method (email or SMS), and an ID proof type for the primary contact before the Visitor Info step can be completed. The system SHALL require the contact field matching the selected preferred contact method — email address when "email" is selected, phone number when "SMS" is selected — but SHALL NOT require the other contact field to also be filled in.

#### Scenario: Missing a required primary contact field blocks progression
- **WHEN** the staff member attempts to proceed without full name, visitor category, preferred contact method, or ID proof type filled in for the primary contact
- **THEN** the system blocks progression and indicates which fields are missing

#### Scenario: Missing the contact field for the selected preferred contact method blocks progression
- **WHEN** the staff member selects "Email" as the preferred contact method but leaves email address blank, or selects "SMS" but leaves phone number blank
- **THEN** the system blocks progression and indicates the missing contact field

#### Scenario: Phone-only primary contact with SMS preferred is accepted
- **WHEN** the staff member selects "SMS" as the preferred contact method, fills in phone number, and leaves email address blank
- **THEN** the system allows progression past the Visitor Info step

#### Scenario: Email-only primary contact with email preferred is accepted
- **WHEN** the staff member selects "Email" as the preferred contact method, fills in email address, and leaves phone number blank
- **THEN** the system allows progression past the Visitor Info step

### Requirement: Added group visitors appear in an editable list
The system SHALL show every visitor added to a group registration in a list displaying each visitor's position, full name, email or phone, and ID proof type, with actions to edit or remove that visitor. Adding a visitor to a group registration SHALL require full name and ID proof type, and at least one of email or phone, but SHALL NOT require both email and phone.

#### Scenario: Added visitor appears in the list
- **WHEN** the staff member submits the "Add to List" form with valid visitor details
- **THEN** the visitor appears in the group visitor list with their position, full name, email or phone, and ID proof type

#### Scenario: Visitor is removed from the list
- **WHEN** the staff member removes a visitor from the group visitor list
- **THEN** that visitor no longer appears in the list or in the submitted request

#### Scenario: Missing both email and phone blocks adding a visitor
- **WHEN** the staff member attempts to add a visitor with neither email nor phone filled in
- **THEN** the system blocks the addition and indicates a reachable contact is required

#### Scenario: Phone-only visitor is accepted into the group list
- **WHEN** the staff member adds a visitor with a phone number and no email address
- **THEN** the visitor is added to the group visitor list

## ADDED Requirements

### Requirement: Profile image can optionally be captured for the primary contact
The system SHALL let the staff member attach an image as a profile photo for the primary contact. The system SHALL NOT require a profile image before the Visitor Info step can be completed. The system SHALL reject files that are not PNG or JPG, or that exceed 5MB. When a profile image is supplied, the system SHALL include it in the submitted registration request.

#### Scenario: Registration proceeds without a profile image
- **WHEN** the staff member completes the Visitor Info step without attaching a profile image for the primary contact
- **THEN** the system allows progression past the Visitor Info step

#### Scenario: Valid profile image is accepted and submitted
- **WHEN** the staff member selects a PNG or JPG file under 5MB as a profile image for the primary contact and submits the registration
- **THEN** the system accepts the file and includes it in the submitted request

#### Scenario: Oversized or unsupported profile image is rejected
- **WHEN** the staff member selects a file over 5MB or with an unsupported type as a profile image
- **THEN** the system rejects the file and explains why, without associating it with the primary contact's entry
