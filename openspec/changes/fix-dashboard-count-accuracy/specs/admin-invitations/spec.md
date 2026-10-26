## MODIFIED Requirements

### Requirement: The admin board opens a status from a deep link
The system SHALL, when the admin Invitations board is opened with one or
more `status` query parameters naming known invitation statuses
(`submitted`, `approved`, `checked_in`, `checked_out`, `denied` or
`archived`), apply those statuses as the status filter once on load,
exactly as if the admin had picked them in the filter bar. Unknown `status`
values SHALL be ignored; if none is known, the board loads with no status
filter.

The board SHALL also accept the dashboard drill-down parameters
`visitDateFrom`, `visitDateTo`, `upcoming=true`, `excludeExpired=true` and
`branchId`. It SHALL send them on every column request and on export, and
SHALL show them as one "From dashboard" row of removable chips (for example
"Visit date: 26 Oct", "Upcoming only", "Not expired", "Branch: HQ"), with
the branch shown by name. A malformed value SHALL be ignored with no error.

The admin SHALL be able to clear or change every one of these afterwards:
removing a chip drops that parameter, and "Clear filters" removes the
status filter and every chip. A `status` and an `invitationId` parameter
SHALL work together: the filter applies, and that invitation's details
open.

#### Scenario: Open pending approvals from the dashboard
- **WHEN** an admin opens `/admin/invitations?status=submitted`
- **THEN** the board shows only submitted invitations, and the status filter
  shows that status

#### Scenario: Several statuses and a visit date
- **WHEN** an admin opens
  `/admin/invitations?status=approved&status=checked_in&status=checked_out&visitDateFrom=2026-10-26&visitDateTo=2026-10-26`
- **THEN** the status filter shows the three statuses, a "Visit date: 26
  Oct" chip is shown, and every column lists only invitations visiting on
  that day

#### Scenario: Removing a chip widens the board
- **WHEN** an admin removes the "Not expired" chip from a board opened with
  `status=submitted&excludeExpired=true`
- **THEN** the board reloads and shows every submitted invitation,
  including expired ones

#### Scenario: Export follows the drill-down
- **WHEN** an admin exports from a board opened with `upcoming=true` and a
  branch chip
- **THEN** the export contains exactly the invitations the board shows

#### Scenario: Unknown status ignored
- **WHEN** an admin opens `/admin/invitations?status=bogus`
- **THEN** the board loads unfiltered, with no error
