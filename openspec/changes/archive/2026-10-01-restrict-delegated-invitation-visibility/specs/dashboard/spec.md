## ADDED Requirements

### Requirement: Dashboard Endpoints Require Branch-Wide Invitation Visibility
`GET /admin/dashboard/overview`, `GET /admin/dashboard/checkins`, and
`GET /admin/dashboard/search` SHALL resolve their branch scope against
`invitations:view-all` rather than `invitations:view`: wherever the
"Dashboard Overview Summary", check-ins, and "Dashboard Topbar Search"
requirements say the caller SHALL hold `invitations:view` at a branch (or
aggregate across every branch they hold it at), the permission consulted
SHALL be `invitations:view-all`. These endpoints aggregate or search across
every invitation at a branch, which only a branch-wide viewer (Reception,
Security, Admin) may see; a caller holding only `invitations:view` (e.g. a
`host`) SHALL be rejected the same way a caller with no grant is today.

#### Scenario: A host cannot search visitor names branch-wide
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/search?query=carter`
- **THEN** the system returns 403 and no invitation data

#### Scenario: A host cannot read branch-wide dashboard counts
- **WHEN** a caller holding only the `host` role at a branch requests
  `GET /admin/dashboard/overview` or `GET /admin/dashboard/checkins`
- **THEN** the system returns 403

#### Scenario: Branch-wide viewers keep the dashboard
- **WHEN** a caller holding the `admin`, `reception`, or `security` role at
  a branch requests any of the three dashboard endpoints scoped to it
- **THEN** the system returns the same data it returned before this change
