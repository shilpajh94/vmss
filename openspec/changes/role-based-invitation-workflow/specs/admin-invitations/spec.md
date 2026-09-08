## MODIFIED Requirements

### Requirement: Card expand, approve, reschedule, and deny behave the same as the staff dashboard
The system SHALL provide, on this page, the same card-expansion (with step-progress and pending-approver display), drag-to-approve (direct or step-based), drag-to-deny (with a required reason, direct or step-based), reschedule, edit, and delegate behaviors specified for the staff-dashboard capability's board, unchanged — including the unassigned-host placeholder, the Edit button and modal, and the unfiltered host picker for the invitation-ownership step's delegation.

#### Scenario: Approve, reschedule, and deny available to admins
- **WHEN** an admin interacts with a card on the Invitations page the same way a staff member would on the staff dashboard
- **THEN** the same approve, reschedule, and deny behaviors apply, with the same success and failure notifications

#### Scenario: Edit and delegate available to admins
- **WHEN** an admin activates Edit or Delegate on a card on the Invitations page
- **THEN** the same edit and delegate behaviors specified for the staff dashboard apply, including the unfiltered host picker for the invitation-ownership step, with the same success and failure notifications
