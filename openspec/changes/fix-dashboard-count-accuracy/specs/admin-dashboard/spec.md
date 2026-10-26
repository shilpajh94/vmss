## MODIFIED Requirements

### Requirement: View All on Recent Check-ins opens the checked-in board
The system SHALL, when "View All" on Recent Check-ins is activated,
navigate to the admin invitations board filtered to both statuses the card
lists, checked-in and checked-out visitors
(`/admin/invitations?status=checked_in&status=checked_out`), adding the
selected branch (`branchId`) when one is selected.

#### Scenario: View All activated
- **WHEN** an admin activates "View All" on Recent Check-ins
- **THEN** the system navigates to
  `/admin/invitations?status=checked_in&status=checked_out` and the board
  shows the Checked-in and Checked-out invitations
