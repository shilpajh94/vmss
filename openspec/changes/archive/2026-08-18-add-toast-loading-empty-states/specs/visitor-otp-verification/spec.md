## ADDED Requirements

### Requirement: OTP request failure also triggers a notification
The system SHALL trigger an error notification when the OTP request fails to complete (network error or non-success response), separate from the generic confirmation shown on success.

#### Scenario: OTP request fails
- **WHEN** an OTP request cannot be completed
- **THEN** the system triggers an error notification and remains on the OTP-request screen

### Requirement: Successful verification also triggers a notification
The system SHALL trigger a success notification when a submitted code is successfully verified, in addition to advancing into the visitor request wizard.

#### Scenario: Code verifies successfully
- **WHEN** the visitor's code is successfully verified
- **THEN** the system triggers a success notification as it renders the visitor request wizard

### Requirement: Failed verification also triggers a notification
The system SHALL, in addition to the inline error on the OTP-verify screen, trigger an error notification when a submitted code does not verify.

#### Scenario: Invalid or expired code
- **WHEN** the visitor submits a code that does not verify
- **THEN** the system shows the inline error message and also triggers an error notification
