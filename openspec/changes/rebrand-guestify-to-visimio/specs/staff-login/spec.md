## MODIFIED Requirements

### Requirement: Staff login screen is visually distinct from the visitor portal
The system SHALL give the admin sign-in screen its own brand panel, distinct from the visitor portal's light header. It SHALL NOT reuse the visitor portal's header component.

The brand panel SHALL show:
- the lobby photo under a navy gradient overlay;
- the Visimio on-dark logo (mark plus white wordmark);
- a headline and a one-line tagline;
- three product highlights, each with an icon and a short label;
- the copyright line.

The screen SHALL NOT show a system-status indicator. Nothing on this page checks system health, so the indicator would be a static, unverified claim.

#### Scenario: Staff screen does not show the visitor header
- **WHEN** the admin sign-in screen renders in a viewport at least 1024px wide
- **THEN** the visitor portal's light header is not present, and the brand panel is shown instead, with the Visimio on-dark logo, a headline, three product highlights, and the copyright line

#### Scenario: No static status claim
- **WHEN** the admin sign-in screen renders
- **THEN** no "All Systems Operational" or other system-status indicator is shown
