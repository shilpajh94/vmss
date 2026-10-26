## ADDED Requirements

### Requirement: The admin board opens a status from a deep link
The system SHALL, when the admin Invitations board is opened with a
`status` query parameter naming a known invitation status (`submitted`,
`approved`, `checked_in`, `checked_out`, `denied` or `archived`), apply
that status filter once on load, exactly as if the admin had picked it in
the filter bar. The admin SHALL be able to clear or change it afterwards.
An unknown `status` value SHALL be ignored, leaving the board unfiltered. A
`status` and an `invitationId` parameter SHALL work together: the filter
applies, and that invitation's details open.

#### Scenario: Open pending approvals from the dashboard
- **WHEN** an admin opens `/admin/invitations?status=submitted`
- **THEN** the board shows only submitted invitations, and the status filter
  shows that status

#### Scenario: Unknown status ignored
- **WHEN** an admin opens `/admin/invitations?status=bogus`
- **THEN** the board loads unfiltered, with no error
