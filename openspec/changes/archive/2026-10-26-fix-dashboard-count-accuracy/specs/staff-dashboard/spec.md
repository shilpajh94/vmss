## MODIFIED Requirements

### Requirement: The staff board opens a status from a deep link
The system SHALL, when the staff Invitations board is opened with one or
more `status` query parameters naming known invitation statuses
(`submitted`, `approved`, `checked_in`, `checked_out`, `denied` or
`archived`), apply those statuses as the status filter once on load,
exactly as if the user had picked them in the filter bar. Unknown `status`
values SHALL be ignored; if none is known, the board loads with no status
filter.

The board SHALL also accept `visitDateFrom`, `visitDateTo`, `upcoming=true`,
`excludeExpired=true` and `branchId`, send them on every column request and
on export, and show them as the same removable "From dashboard" chips as
the admin board. These parameters SHALL only narrow the user's own visits
and SHALL never show an invitation the board would not otherwise show. A
malformed value SHALL be ignored with no error. The user SHALL be able to
clear or change every one of them afterwards.

#### Scenario: Open the checked-in visitors from a dashboard
- **WHEN** a staff member opens `/staff/invitations?status=checked_in`
- **THEN** the board shows only checked-in invitations, and the status
  filter shows "Checked in"

#### Scenario: Open awaiting approvals that are still open
- **WHEN** a staff member opens
  `/staff/invitations?status=submitted&excludeExpired=true`
- **THEN** the board shows only their own submitted invitations whose visit
  window is still open, with a "Not expired" chip

#### Scenario: Unknown status ignored
- **WHEN** a staff member opens `/staff/invitations?status=bogus`
- **THEN** the board loads unfiltered, with no error
