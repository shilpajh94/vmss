## ADDED Requirements

### Requirement: The sidebar footer shows the real build identifier
The admin sidebar footer SHALL show the deployed build's identifier: the
application version and, when available, the short source revision it was
built from (for example "v1.3.0 · 3fa9c21"). Both SHALL be injected at build
time. The footer SHALL NOT show a hardcoded version or a status indicator
that reflects no real health check. When neither value is available, the
footer line SHALL be omitted.

#### Scenario: Build identifier shown
- **WHEN** the portal is built with version 1.3.0 from revision 3fa9c21 and
  an admin opens any admin page
- **THEN** the sidebar footer reads "v1.3.0 · 3fa9c21", with no "Active"
  status dot

#### Scenario: Collapsed rail
- **WHEN** the desktop sidebar is collapsed to its icon rail
- **THEN** the build identifier is hidden, and the rail does not overflow
