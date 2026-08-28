## ADDED Requirements

### Requirement: Duplicate Branch-Role Grant Assignment Is Rejected
Granting a user a role at a branch scope (a specific branch, or company-wide
when no branch is given) that the user already holds that exact role at
SHALL be rejected with 409, leaving the existing grant unchanged and
creating no second `UserBranchRole` row.

#### Scenario: Assigning an identical grant a second time is rejected
- **WHEN** a caller with `users:manage` grants a role to a user at a branch
  scope the user already holds that same role at
- **THEN** the request is rejected with 409, the user's existing grant is
  unchanged, and no duplicate `UserBranchRole` row is created
