## MODIFIED Requirements

### Requirement: Successful verification proceeds into the visitor request wizard
The system SHALL, when verification succeeds, use the returned proof token to look up the visitor's return-visit history and prefill profile before deciding what to render next: if the lookup finds prior visits, the system SHALL render the return-visit history screen; otherwise the system SHALL render the visitor request wizard with its registration type and primary contact (mobile number or email) pre-filled from the OTP flow, and, when a prefill profile is available, with the wizard's full-profile fields pre-filled per the visitor-request-wizard capability.

#### Scenario: Verified visitor reaches the wizard with pre-filled data
- **WHEN** the visitor's code is successfully verified and the history lookup finds no prior visits
- **THEN** the system renders the first step of the visitor request wizard with the registration type selected on the OTP-request screen and the verified contact already filled into the corresponding primary-contact field, without showing a history screen

#### Scenario: Verified visitor with prior visits sees history before the wizard
- **WHEN** the visitor's code is successfully verified and the history lookup finds one or more prior visits
- **THEN** the system renders the return-visit history screen instead of the visitor request wizard

#### Scenario: History lookup rejects the proof token
- **WHEN** the history lookup responds with 401 (expired or invalid proof token)
- **THEN** the system returns the visitor to the OTP-request screen to request a fresh code, rather than rendering the wizard or the history screen
