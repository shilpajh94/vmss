## MODIFIED Requirements

### Requirement: Visit Info step requires visit-planning details
The system SHALL require purpose of visit, preferred visit date, preferred visit time, expected duration, location, and building before the Visit Info step can be completed. Additional notes are optional. The visitor SHALL NOT be asked to name a host — every invitation is routed to the receiving organisation's front-office team by default, who assign the actual host afterward. The visitor SHALL NOT be asked to pick a department to visit either, for the same reason: a visitor rarely knows the receiving organisation's internal department structure, so front-office staff determine the correct department afterward, once they know the visitor's actual requirements (see the `staff-dashboard` capability's Edit Invitation action).

#### Scenario: Missing a required visit-planning field blocks progression
- **WHEN** the visitor attempts to proceed without purpose, date, time, duration, location, or building filled in
- **THEN** the system blocks progression and indicates which fields are missing

#### Scenario: No host field is shown
- **WHEN** a visitor reaches the Visit Info step
- **THEN** no host name/email field is shown, and none of the step's required fields concern who the host is

#### Scenario: No department field is shown
- **WHEN** a visitor reaches the Visit Info step
- **THEN** no department field is shown, and none of the step's required fields concern which department they are visiting
