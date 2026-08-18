# visitor-otp-verification Specification

## Purpose

The visitor-otp-verification capability lets a visitor prove they control the mobile number or email they're registering with, via a one-time code, before they can start filling out a visit request.

## Requirements

### Requirement: OTP request screen is reachable from the landing page's request entry point
The system SHALL render an OTP-request screen at the visit-request route the landing page's "Request Visit" action navigates to, in place of the visitor request wizard, matching the approved "Request a Visit" design.

#### Scenario: Visitor reaches the OTP-request screen from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders with a registration type toggle, a contact field, and a "Request OTP" action, instead of the visitor request wizard

### Requirement: Visitor selects a registration type before requesting a code
The system SHALL let the visitor choose between "Single visitor" and "Group visitors" registration type on the OTP-request screen, defaulting to "Single visitor".

#### Scenario: Registration type defaults and can be changed
- **WHEN** the visitor opens the OTP-request screen
- **THEN** "Single visitor" is selected by default, and the visitor can switch to "Group visitors" before requesting a code

### Requirement: OTP request requires a non-empty mobile number or email
The system SHALL require a non-empty value in the mobile number/email field before it will request a verification code, and SHALL accept either a mobile number or an email address in that field.

#### Scenario: Empty contact blocks the request
- **WHEN** the visitor activates "Request OTP" with the contact field empty
- **THEN** the system blocks the request and indicates the field is required

#### Scenario: Contact is submitted for a code
- **WHEN** the visitor activates "Request OTP" with a mobile number or email entered
- **THEN** the system requests a one-time verification code for that contact and, on success, shows the OTP-verify screen

### Requirement: OTP request outcome does not reveal whether the contact is known
The system SHALL show the same generic confirmation after a successful OTP request regardless of whether the submitted contact matches an existing visitor record, so the screen cannot be used to enumerate valid contacts.

#### Scenario: Generic confirmation after requesting a code
- **WHEN** an OTP request completes successfully for any syntactically valid contact
- **THEN** the system shows "If that contact is valid, a verification code has been sent to it." and advances to the OTP-verify screen

### Requirement: OTP request failure also triggers a notification
The system SHALL trigger an error notification when the OTP request fails to complete (network error or non-success response), separate from the generic confirmation shown on success.

#### Scenario: OTP request fails
- **WHEN** an OTP request cannot be completed
- **THEN** the system triggers an error notification and remains on the OTP-request screen

### Requirement: OTP-verify screen requires a verification code to proceed
The system SHALL render an OTP-verify screen after a successful OTP request, with a verification-code field and a "Verify and continue" action, and SHALL require a non-empty code before attempting verification.

#### Scenario: Empty code blocks verification
- **WHEN** the visitor activates "Verify and continue" with the code field empty
- **THEN** the system blocks verification and indicates the field is required

#### Scenario: Code is submitted for verification
- **WHEN** the visitor activates "Verify and continue" with a code entered
- **THEN** the system attempts to verify that code against the requested contact

### Requirement: Successful verification proceeds into the visitor request wizard
The system SHALL, when verification succeeds, render the visitor request wizard with its registration type and primary contact (mobile number or email) pre-filled from the OTP flow.

#### Scenario: Verified visitor reaches the wizard with pre-filled data
- **WHEN** the visitor's code is successfully verified
- **THEN** the system renders the first step of the visitor request wizard with the registration type selected on the OTP-request screen and the verified contact already filled into the corresponding primary-contact field

### Requirement: Successful verification also triggers a notification
The system SHALL trigger a success notification when a submitted code is successfully verified, in addition to advancing into the visitor request wizard.

#### Scenario: Code verifies successfully
- **WHEN** the visitor's code is successfully verified
- **THEN** the system triggers a success notification as it renders the visitor request wizard

### Requirement: Failed verification is reported without losing the OTP session
The system SHALL, when a submitted code is invalid or expired, show an error on the OTP-verify screen and let the visitor retry without re-requesting a code.

#### Scenario: Invalid or expired code
- **WHEN** the visitor submits a code that does not verify
- **THEN** the system shows an error message, remains on the OTP-verify screen, and lets the visitor submit another code

### Requirement: Failed verification also triggers a notification
The system SHALL, in addition to the inline error on the OTP-verify screen, trigger an error notification when a submitted code does not verify.

#### Scenario: Invalid or expired code
- **WHEN** the visitor submits a code that does not verify
- **THEN** the system shows the inline error message and also triggers an error notification

### Requirement: Visitor can restart with a different contact
The system SHALL let the visitor return from the OTP-verify screen to the OTP-request screen to submit a different mobile number or email.

#### Scenario: Visitor switches contact
- **WHEN** the visitor activates "Use a different number or email" on the OTP-verify screen
- **THEN** the system returns to the OTP-request screen, ready to accept a new contact and registration type

### Requirement: OTP screens share the portal's visual theme
The system SHALL render the OTP-request and OTP-verify screens with the same header, footer, and design-theme tokens (color, typography) used by the landing page and visitor request wizard.

#### Scenario: Consistent chrome across the request flow
- **WHEN** a visitor moves from the landing page through the OTP screens into the visitor request wizard
- **THEN** the header, footer, and visual styling remain visually consistent across all screens
