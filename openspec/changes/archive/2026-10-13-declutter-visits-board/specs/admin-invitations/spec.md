## MODIFIED Requirements

### Requirement: Card expand, approve, reschedule, and deny behave the same as the staff dashboard
The system SHALL provide on this page the same card behaviours specified for the staff-dashboard capability's board, unchanged:
- activating a card opens Visitor Info
- the "Level X/Y · Pending" approval badge
- card-face Approve/Deny buttons and drag-to-approve (direct or step-based)
- drag-to-deny, with a required reason (direct or step-based)
- the Visitor info, Reschedule, Edit, and Delegate icon buttons and the modals they open

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same success and failure notifications

#### Scenario: Activating a card opens Visitor Info
- **WHEN** an admin clicks a card on the Invitations board outside its buttons
- **THEN** the Visitor Info modal opens for that invitation, and the card does not expand
