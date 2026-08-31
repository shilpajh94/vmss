# visitor-request-wizard Specification

## Purpose

The visitor-request-wizard capability lets a visitor submit everything a host organization needs to issue a visitor pass — who is visiting, why, what they're carrying, and what they consent to — across a guided multi-step form, and tells them whether it was accepted.

## Requirements

### Requirement: Wizard is reachable from the landing page's request entry point
The system SHALL render the visitor request wizard only after a visitor has successfully completed OTP verification, pre-filled with the registration type and contact captured during verification. The wizard SHALL NOT render directly from the landing page's "Request Visit" action.

#### Scenario: Visitor reaches the wizard from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page and successfully completes OTP verification
- **THEN** the first step of the visitor request wizard ("Visitor Info") renders, with registration type and the verified contact's mobile number or email already filled in

#### Scenario: Wizard does not render before verification
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders, and the visitor request wizard does not render until verification succeeds

### Requirement: Visitor chooses between an individual and a group registration
The system SHALL let the visitor declare whether the request is for a single visitor or a group, and SHALL show the fields appropriate to that choice.

#### Scenario: Individual registration shows a single visitor's fields
- **WHEN** the visitor selects "Individual"
- **THEN** the form shows one set of fields for full name, email, phone, address, visitor category, preferred contact method, ID proof, and profile image

#### Scenario: Group registration shows a primary contact and a visitor list
- **WHEN** the visitor selects "Group"
- **THEN** the form shows primary contact fields plus a list of additional visitors, each addable with their own full name, email, phone, address, visitor category, ID proof, and profile image

#### Scenario: Group registration requires at least one visitor in the list
- **WHEN** the visitor attempts to proceed from a Group registration with zero visitors added to the list
- **THEN** the system blocks progression and indicates at least one visitor must be added

### Requirement: Visitor Info step requires core contact and address details
The system SHALL require full name, email, phone number, address, visitor category, and ID proof type before the Visitor Info step can be completed, for the individual visitor or for the primary contact and every added group visitor.

#### Scenario: Missing a required contact field blocks progression
- **WHEN** the visitor attempts to proceed without full name, email, phone, address, visitor category, or ID proof type filled in
- **THEN** the system blocks progression and indicates which fields are missing

### Requirement: ID proof and profile image can optionally be uploaded as supporting documents
The system SHALL let the visitor attach an image or PDF as ID proof, and separately an image as a profile photo, for themselves (individual) or for any visitor in the list (group). The system SHALL reject files that are not PNG, JPG, or PDF, or that exceed 5MB, for either upload.

#### Scenario: Valid ID document is accepted
- **WHEN** the visitor selects a PNG, JPG, or PDF file under 5MB as ID proof
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Valid profile image is accepted
- **WHEN** the visitor selects a PNG or JPG file under 5MB as a profile image
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Oversized or unsupported file is rejected
- **WHEN** the visitor selects a file over 5MB or with an unsupported type for either ID proof or profile image
- **THEN** the system rejects the file and explains why, without associating it with the visitor's entry

### Requirement: Visit Info step requires visit-planning details
The system SHALL require purpose of visit, host name or email, preferred visit date, preferred visit time, expected duration, location, building, and department to visit before the Visit Info step can be completed. Additional notes are optional.

#### Scenario: Missing a required visit-planning field blocks progression
- **WHEN** the visitor attempts to proceed without purpose, host, date, time, duration, location, building, or department filled in
- **THEN** the system blocks progression and indicates which fields are missing

### Requirement: Carried Items step declares security-relevant items without requiring any
The system SHALL let the visitor declare zero or more carried item categories, with an optional free-text description, and SHALL allow progression whether or not any category is selected.

#### Scenario: No items declared is a valid declaration
- **WHEN** the visitor proceeds from the Carried Items step with no category selected
- **THEN** the system allows progression, recording that no items were declared

### Requirement: Vehicle Info step records zero or more vehicles
The system SHALL let the visitor add zero or more vehicles, each requiring vehicle type, license plate, make/model, and color when added, and SHALL allow progression with an empty vehicle list.

#### Scenario: Adding a vehicle requires its details
- **WHEN** the visitor attempts to add a vehicle without vehicle type, license plate, make/model, or color filled in
- **THEN** the system blocks adding that vehicle and indicates which fields are missing

#### Scenario: No vehicles declared is valid
- **WHEN** the visitor proceeds from the Vehicle Info step with no vehicle added
- **THEN** the system allows progression

### Requirement: Consent Agreement step requires all three acknowledgements
The system SHALL require the visitor to check all three consent acknowledgements (terms & conditions, personal data use, safety guidelines) before the Consent Agreement step can be completed.

#### Scenario: Unchecked consent blocks progression
- **WHEN** the visitor attempts to proceed with any of the three consent checkboxes unchecked
- **THEN** the system blocks progression

### Requirement: Review step summarizes the request before submission
The system SHALL present a summary of every prior step's entered data on the final step, and SHALL only submit the request when the visitor explicitly confirms.

#### Scenario: Review shows entered data
- **WHEN** the visitor reaches the Review & Confirm step
- **THEN** the summary reflects the visitor info (including address, visitor category, and profile image), visit info (including location and building), carried items, vehicles, and consent state entered in the prior steps

#### Scenario: Visitor can return to an earlier step from review
- **WHEN** the visitor chooses to go back from the Review & Confirm step
- **THEN** the system returns to the previous step with all previously entered data intact

### Requirement: The primary contact's visitor category is submitted as the invitation's category
The system SHALL submit the primary contact's selected visitor category as the invitation-level visitor category, identified by that category's id, since the backend associates one visitor category with an invitation as a whole rather than per visitor.

#### Scenario: Submission includes the invitation's visitor category
- **WHEN** the visitor confirms submission
- **THEN** the submitted request includes the primary contact's selected visitor category's id as the invitation's visitor category

### Requirement: Submission reports success with a tracking reference
The system SHALL, on successful submission, show the visitor a confirmation containing a tracking reference for the request.

#### Scenario: Successful submission
- **WHEN** the visitor confirms submission and the request is accepted
- **THEN** the system shows a confirmation screen containing a tracking reference for the submitted request

### Requirement: Submission failure is reported without losing entered data
The system SHALL, when submission fails, show the visitor an error and SHALL preserve all entered data so the visitor can retry without re-entering it.

#### Scenario: Submission fails
- **WHEN** the visitor confirms submission and the request is rejected or the submission cannot be completed
- **THEN** the system shows an error message, remains on the Review & Confirm step, and retains all previously entered data for a retry
