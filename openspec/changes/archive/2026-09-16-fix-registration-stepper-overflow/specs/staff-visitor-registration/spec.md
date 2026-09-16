## ADDED Requirements

### Requirement: Every step in the progress stepper stays visible and reachable regardless of viewport width or zoom level
The stepper SHALL keep every active step (however many the branch's
published form configuration includes) visible and directly reachable at
any browser zoom level or viewport width, without relying on an
undiscoverable horizontal scroll as the only way to reach a step past the
visible edge. If the stepper cannot fit every step on one row at the
current width, it SHALL either wrap steps onto additional rows, switch to
a more compact per-step presentation, or provide a visible scroll
affordance (not a bare, easy-to-miss scrollbar) indicating more steps exist
off-screen.

#### Scenario: A branch with many steps stays fully visible at reduced zoom
- **WHEN** a branch's published form configuration has enough active steps
  that their combined width would exceed a fixed-width row at the current
  browser zoom level
- **THEN** every step remains visible (via wrapping, a compact
  presentation, or a discoverable scroll affordance) rather than being
  clipped behind an unindicated horizontal scroll

#### Scenario: All steps remain individually reachable
- **WHEN** the wizard renders at any viewport width or browser zoom level
- **THEN** the user can navigate to any active step via the stepper without
  needing to guess that off-screen content exists
