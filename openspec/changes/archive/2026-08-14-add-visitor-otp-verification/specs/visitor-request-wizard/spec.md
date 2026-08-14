## MODIFIED Requirements

### Requirement: Wizard is reachable from the landing page's request entry point
The system SHALL render the visitor request wizard only after a visitor has successfully completed OTP verification, pre-filled with the registration type and contact captured during verification. The wizard SHALL NOT render directly from the landing page's "Request Visit" action.

#### Scenario: Visitor reaches the wizard from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page and successfully completes OTP verification
- **THEN** the first step of the visitor request wizard ("Visitor Info") renders, with registration type and the verified contact's mobile number or email already filled in

#### Scenario: Wizard does not render before verification
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders, and the visitor request wizard does not render until verification succeeds
