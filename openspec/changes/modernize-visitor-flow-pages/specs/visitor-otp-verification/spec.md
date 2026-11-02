## MODIFIED Requirements

### Requirement: OTP screens share the portal's visual theme
The system SHALL render the OTP-request and OTP-verify screens on the same split-screen layout and design-theme tokens (colour, typography) as the landing page and visitor request wizard (see `public-page-layout`). Specifically:
- the same navy brand panel or top strip;
- the same footer links;
- the same back action;
- the same form styling.

#### Scenario: Consistent chrome across the request flow
- **WHEN** a visitor moves from the landing page through the OTP screens into the visitor request wizard
- **THEN** the navy brand panel (or top strip), the footer links, and the visual styling remain visually consistent across all screens, with no white header or footer bar on any of them
