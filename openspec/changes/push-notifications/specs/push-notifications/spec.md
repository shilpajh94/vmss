## Purpose

The push-notifications capability delivers real-time browser push notifications about invitation lifecycle events (new approval requests, approvals, denials, reschedules) to signed-in staff, via Firebase Cloud Messaging, and routes a click on one to the relevant invitation.

## ADDED Requirements

### Requirement: A signed-in staff device is registered for push notifications
The system SHALL request the browser's notification permission and, once granted, obtain a Firebase Cloud Messaging token and register it with the backend as soon as a staff member signs in (via `/admin/login` or SSO). Registration SHALL happen without blocking or failing the sign-in flow.

#### Scenario: Staff signs in and grants notification permission
- **WHEN** a staff member successfully signs in and grants the browser's notification permission
- **THEN** the system obtains an FCM token and registers it with the backend for that staff member's session

#### Scenario: Staff signs in and denies or has not decided on notification permission
- **WHEN** a staff member successfully signs in and the browser's notification permission is denied or not yet granted
- **THEN** the system completes sign-in normally and does not register a device

#### Scenario: Device registration request fails
- **WHEN** the device-registration request to the backend fails
- **THEN** the system leaves the staff member signed in and does not surface an error that blocks their use of the dashboard

### Requirement: A rotated FCM token is re-registered
The system SHALL detect when Firebase issues a new FCM token for an already-registered, signed-in staff device and register the new token with the backend.

#### Scenario: Firebase rotates the token during an active session
- **WHEN** Firebase issues a new FCM token while a staff member has an active, permission-granted session
- **THEN** the system registers the new token with the backend

### Requirement: A device is unregistered on sign-out
The system SHALL unregister the current device's FCM token with the backend as part of staff sign-out, before the session's auth token is cleared.

#### Scenario: Staff signs out with a registered device
- **WHEN** a staff member with a registered device signs out
- **THEN** the system requests unregistration of that device's FCM token, then clears the session and navigates to the sign-in screen

#### Scenario: Staff signs out with no registered device
- **WHEN** a staff member who never granted notification permission (or was never registered) signs out
- **THEN** the system clears the session and navigates to the sign-in screen without attempting to unregister a device

### Requirement: A foreground push notification is shown as an in-app notification
The system SHALL display an incoming push notification as an in-app notification when the browser tab is focused (foreground), instead of relying on the operating system's native notification.

#### Scenario: Push arrives while the staff member has the tab open
- **WHEN** a push notification about an invitation lifecycle event arrives while the dashboard tab is focused
- **THEN** the system shows an in-app notification with the event's message

### Requirement: A background push notification is shown by the OS
The system SHALL display an incoming push notification as a native operating-system notification when the browser tab is not focused or the browser is closed.

#### Scenario: Push arrives while the tab is backgrounded or closed
- **WHEN** a push notification about an invitation lifecycle event arrives while the dashboard tab is not focused or the browser is closed
- **THEN** the operating system displays a native notification with the event's message

### Requirement: Clicking a push notification navigates to the related invitation
The system SHALL navigate the staff member to the detail view of the invitation referenced by a push notification when they click it, whether the notification was shown in-app or by the operating system.

#### Scenario: Staff clicks an in-app notification
- **WHEN** a staff member clicks an in-app notification for an invitation lifecycle event
- **THEN** the system navigates to that invitation's detail view

#### Scenario: Staff clicks an OS-level notification
- **WHEN** a staff member clicks an operating-system notification for an invitation lifecycle event
- **THEN** the system focuses or opens the app and navigates to that invitation's detail view
