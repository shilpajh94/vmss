## ADDED Requirements

### Requirement: A push notification distinguishes role-addressed from person-addressed delivery
The system SHALL render an incoming push notification (in-app or OS-level) differently depending on the addressing metadata the payload carries (`assignedRoleId`/`assignedUserId`/`reason`, per the `VMSS_API` change's `notifications` capability delta): a `role_assigned` notification SHALL be labeled with the role it was sent to (e.g. "New invitation for Front Office"), and a `delegated` notification SHALL be labeled to make clear it was assigned to the viewing staff member personally (e.g. "Delegated to you"). This applies to both the in-app notification and the notification-center/bell list item it produces, not only the OS-level notification. NOTE: this capability's own code is implemented but not yet archived into `openspec/specs/` (see `openspec/changes/push-notifications/`); this delta assumes that change has landed first and targets the resulting capability — reconcile the two at whichever archives second if they land out of order.

#### Scenario: Role-addressed push is labeled with the role
- **WHEN** a push notification arrives whose payload has `reason: "role_assigned"` and an `assignedRoleId`
- **THEN** both the in-app/OS notification and its notification-center entry are labeled with that role's name, not a specific person

#### Scenario: Person-addressed push is labeled as delegated to the viewer
- **WHEN** a push notification arrives whose payload has `reason: "delegated"` and an `assignedUserId` matching the signed-in staff member
- **THEN** both the in-app/OS notification and its notification-center entry are labeled to indicate it was assigned to them personally (e.g. "Delegated to you"), distinct from a role-addressed notification's label
