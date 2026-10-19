## MODIFIED Requirements

### Requirement: Card expand, approve, reschedule, and deny behave the same as the staff dashboard
The system SHALL provide on this page the same card behaviours specified for the staff-dashboard capability's board, unchanged:
- activating a card opens Visitor Info, including the "Approval reverted" note for a reverted request
- the "Level X/Y · Pending" approval badge
- card-face Approve/Deny buttons and drag-to-approve (direct or step-based), each approval sent only after confirmation
- drag-to-deny, with a required reason (direct or step-based)
- the Visitor info, Reschedule, Edit, Delegate, and Revert approval icon buttons and the modals they open
- the rule that every invitation action is confirmed before its request is sent, including the summary confirmation for form-based actions and pausing background refresh while a confirmation is open or in flight

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same confirmations and the same success and failure notifications

#### Scenario: Admins can revert an approval
- **WHEN** an admin activates "Revert approval" on an Approved card, enters a reason, and confirms
- **THEN** the same revert behavior as the staff dashboard applies, and the card moves back to the Requested column after the board reloads

#### Scenario: Activating a card opens Visitor Info
- **WHEN** an admin clicks a card on the Invitations board outside its buttons
- **THEN** the Visitor Info modal opens for that invitation, and the card does not expand
