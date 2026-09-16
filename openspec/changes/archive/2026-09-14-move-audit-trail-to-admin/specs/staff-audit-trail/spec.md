## REMOVED Requirements

### Requirement: Audit Trail page requires an authenticated staff session
**Reason**: The Audit Trail page moves out of the staff portal entirely; it is replaced by the admin-only, organisation-wide page defined in `admin-audit-trail`.
**Migration**: None. Staff members no longer have an audit trail view; admins use `/admin/audit-trail`.

### Requirement: Page renders the sidebar, workspace header, and audit trail content
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Workspace header shows the signed-in staff member
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Sign out ends the session and returns to login
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Summary stats reflect the signed-in staff member's hosted visitors
**Reason**: Replaced by `admin-audit-trail`'s organisation-wide summary stats.
**Migration**: None.

### Requirement: Date-range filter narrows the activity log
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Activity-type filter narrows the activity log
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Search filters the activity log by visitor name
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Activity log entries show identifying and contextual details
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Status is shown as a labeled pill
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Empty activity log shows an empty-state message
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Activity log is paginated
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: List load failure is reported without crashing
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.

### Requirement: Audit trail load failure also triggers a notification
**Reason**: Superseded by `admin-audit-trail`'s equivalent requirement.
**Migration**: None.
