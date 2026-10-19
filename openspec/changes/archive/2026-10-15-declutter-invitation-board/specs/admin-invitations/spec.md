## ADDED Requirements

### Requirement: Invitations board columns can be collapsed and keep a readable width
The admin Invitations board SHALL offer the same desktop column collapse and minimum column width that the staff dashboard defines in "Status columns can be collapsed on desktop" and "Board columns keep a readable minimum width". The admin board's collapsed columns SHALL be remembered separately from the staff board's, so collapsing a column on one board does not collapse it on the other.

#### Scenario: Collapsing a column on the admin board
- **WHEN** an admin at 1536px wide collapses the Denied column on `/admin/invitations`
- **THEN** Denied renders as a narrow strip with its label and count, and the other columns widen to fill the board

#### Scenario: Admin and staff boards remember independently
- **WHEN** a user collapses Archived on the admin board and then opens the staff Invitations board in the same browser
- **THEN** Archived is expanded on the staff board unless it was collapsed there separately
