## MODIFIED Requirements

### Requirement: Wizard is reachable from the landing page's request entry point
The system SHALL render the visitor request wizard only after a visitor has successfully completed OTP verification (directly, or by activating "Start a new request" on the return-visit history screen), pre-filled with the registration type and contact captured during verification. When the verified visitor has a non-null prefill profile, the wizard SHALL also pre-fill that profile's full name, email, phone, preferred contact method, and ID-proof type for the primary contact. The wizard SHALL NOT render directly from the landing page's "Request Visit" action, and SHALL NOT pre-fill the ID-proof document image or profile photo from a prior visit.

#### Scenario: Visitor reaches the wizard from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page and successfully completes OTP verification
- **THEN** the first step of the visitor request wizard ("Visitor Info") renders, with registration type and the verified contact's mobile number or email already filled in

#### Scenario: Wizard does not render before verification
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders, and the visitor request wizard does not render until verification succeeds

#### Scenario: Returning visitor's wizard is pre-filled from their profile
- **WHEN** a returning visitor starts a new request from the return-visit history screen and their prefill profile is not null
- **THEN** the wizard's Visitor Info step renders with full name, email, phone, preferred contact method, and ID-proof type already filled in for the primary contact, while the ID-proof document image and profile photo remain unfilled and must be provided fresh

#### Scenario: First-time visitor's wizard has no profile prefill
- **WHEN** a visitor is verified and the history lookup's prefill profile is null
- **THEN** the wizard renders with only registration type and contact pre-filled, matching the wizard's existing first-time-visitor behavior
