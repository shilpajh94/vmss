## ADDED Requirements

### Requirement: Branch Deletion Is Blocked for the Configured Walk-In Default Branch
Soft-deleting a `Branch` SHALL be rejected with 409 when that branch's
`code` matches the server's configured walk-in registration default branch
code (`settings.registration_default_branch_code`) — the same referential-
integrity posture already applied to a branch with active org-chart
children or an active registration device credential. A branch whose code
does not match the configured default SHALL be unaffected by this
requirement.

#### Scenario: Deleting the configured default branch is rejected
- **WHEN** a caller with `branches:manage` attempts to delete a `Branch`
  whose `code` matches the configured walk-in registration default branch
  code
- **THEN** the request is rejected with 409 and the branch is left
  undeleted

#### Scenario: A branch that is not the configured default can be deleted freely
- **WHEN** a caller with `branches:manage` deletes a `Branch` whose `code`
  does not match the configured walk-in registration default branch code
- **THEN** the request proceeds exactly as it did before this requirement
  existed
