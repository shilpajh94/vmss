## REMOVED Requirements

### Requirement: Top bar search and notification affordances are presented but not yet functional
**Reason**: The workspace search field is being removed from the shared Admin top bar per stakeholder request; the notification affordance's own behavior is covered by the new "Top bar notification affordance is presented but not yet functional" requirement below.
**Migration**: No admin-facing migration — the top bar simply no longer renders a workspace search field.

## ADDED Requirements

### Requirement: Top bar notification affordance is presented but not yet functional
The system SHALL render the notification indicator in the top bar per the design, but SHALL NOT show notifications when it is activated. The top bar SHALL NOT render a workspace search field.

#### Scenario: Notification indicator activated
- **WHEN** an admin activates the notification indicator
- **THEN** the visible page content does not change

#### Scenario: No workspace search field rendered
- **WHEN** the Organisation Configs page loads
- **THEN** the top bar does not show a workspace search field
