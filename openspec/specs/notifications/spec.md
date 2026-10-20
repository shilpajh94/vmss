# notifications Specification

## Purpose

The notifications capability gives any page a way to surface transient, dismissible success/error/info feedback about the outcome of an action, independent of that page's own layout.

## Requirements

### Requirement: A notification hook is available to any page
The system SHALL expose a hook that any page component can call to trigger a success, error, or info notification, without that page needing to render or manage the notification itself.

#### Scenario: Page triggers a notification
- **WHEN** a page component calls the notification hook with a success, error, or info message
- **THEN** the system displays that notification without the page rendering any notification markup itself

### Requirement: Notifications render as a stacked, dismissible viewport
The system SHALL render active notifications in a single on-screen viewport, stacking multiple concurrent notifications, each independently and manually dismissible, and each visually distinguished by its severity (success, error, info). The viewport SHALL be anchored to the bottom-right corner of the screen at widths of 640px and above, and to the bottom edge below that, so that no notification covers the top bar or any control in it (refresh control, notification bell, user menu). The newest notification SHALL sit closest to the anchored edge.

#### Scenario: Single notification shown
- **WHEN** one notification is triggered
- **THEN** it appears in the viewport styled for its severity, with a control to dismiss it

#### Scenario: Multiple notifications shown concurrently
- **WHEN** a second notification is triggered while the first is still visible
- **THEN** both are shown stacked in the viewport, and dismissing one does not remove the other

#### Scenario: Notifications leave the top bar clear
- **WHEN** a notification is visible on a 1440px-wide staff Invitations page
- **THEN** it appears in the bottom-right corner, and the top bar's refresh control, notification bell and user avatar remain fully visible and clickable

#### Scenario: Notifications on a phone
- **WHEN** a notification is visible on a 390px-wide screen
- **THEN** it spans the bottom of the screen within the page gutters and does not overlap the top bar

### Requirement: Notifications auto-dismiss but can be dismissed early
The system SHALL automatically remove a notification after a fixed duration, and SHALL also remove it immediately if the user manually dismisses it before that duration elapses. While the pointer rests on a notification, or keyboard focus is inside it, its auto-dismiss timer SHALL pause; when the pointer leaves and focus moves out, the notification SHALL stay visible for at least a further two seconds before it auto-dismisses.

#### Scenario: Notification times out
- **WHEN** a notification has been visible for its fixed duration without being manually dismissed
- **THEN** the system removes it from the viewport

#### Scenario: Notification dismissed early
- **WHEN** a user manually dismisses a notification before its duration elapses
- **THEN** the system removes it immediately

#### Scenario: Hovering keeps a notification open
- **WHEN** the user moves the pointer onto an info notification three seconds after it appeared and keeps it there for ten seconds
- **THEN** the notification is still visible, and it auto-dismisses no sooner than two seconds after the pointer leaves

#### Scenario: Keyboard focus keeps a notification open
- **WHEN** the user tabs onto a notification's dismiss control
- **THEN** the notification does not auto-dismiss while focus remains inside it

### Requirement: Notifications are announced to assistive technology
The system SHALL expose each notification through an ARIA live region appropriate to its severity, so that screen readers announce error notifications assertively and success/info notifications politely.

#### Scenario: Error notification is announced
- **WHEN** an error notification is triggered
- **THEN** it is exposed via an `alert`-equivalent live region

#### Scenario: Success or info notification is announced
- **WHEN** a success or info notification is triggered
- **THEN** it is exposed via a `status`-equivalent live region

### Requirement: At most three notifications are visible at once
The system SHALL show no more than three notifications in the viewport at the same time. A notification triggered while three are visible SHALL wait in a first-in, first-out queue and SHALL appear when a visible one leaves. A queued notification's auto-dismiss duration SHALL start only when it becomes visible. No notification, including an error, SHALL be discarded because the viewport was full.

#### Scenario: A fourth notification waits its turn
- **WHEN** three notifications are visible and a fourth is triggered
- **THEN** the fourth is not shown yet, and when any of the three is dismissed or expires, the fourth appears

#### Scenario: Queued notifications keep their order
- **WHEN** three notifications are visible and two more, A then B, are triggered
- **THEN** A appears before B as space frees up

#### Scenario: A queued error is not lost
- **WHEN** three success notifications are visible and an error notification is triggered
- **THEN** the error appears once a slot frees and stays for its full error duration from that moment

### Requirement: A burst of push notifications is grouped into one summary
The system SHALL group foreground push notifications so that a burst never produces more than one notification in the viewport. A push that arrives while no push notification is showing SHALL appear as its own notification with its message, and activating it SHALL open its invitation, as before. A push that arrives while a push notification is still showing (or queued) SHALL NOT add another notification; instead the existing one SHALL become a summary reading "N new notifications", where N counts every push in the group, and its count SHALL update in place as more arrive. Each push that joins the group SHALL restart the summary's auto-dismiss duration. Activating the summary SHALL open the notification bell's panel, where each grouped notification is listed individually, and SHALL dismiss the summary. Grouping SHALL apply only to push notifications; success, error and info feedback from the user's own actions SHALL never be merged into the summary. The summary SHALL be announced to assistive technology politely, and a count update SHALL NOT re-announce every intermediate number in a rapid burst.

#### Scenario: A single push
- **WHEN** one foreground push for a new invitation arrives and no push notification is showing
- **THEN** a notification shows that push's message, and clicking it opens that invitation

#### Scenario: Ten pushes arrive together
- **WHEN** ten foreground pushes arrive within two seconds
- **THEN** the viewport shows exactly one push notification reading "10 new notifications", not ten stacked notifications

#### Scenario: A push joins a visible one
- **WHEN** a push notification is showing and another push arrives
- **THEN** the visible notification changes to "2 new notifications" in place, without a new notification sliding in

#### Scenario: Opening the summary
- **WHEN** the user clicks a "5 new notifications" summary
- **THEN** the notification bell's panel opens listing the new notifications, and the summary is dismissed

#### Scenario: Action feedback stays separate
- **WHEN** a "Visit request approved." success notification is showing and three pushes arrive
- **THEN** the success notification remains as it was, and the pushes appear as one separate "3 new notifications" summary

#### Scenario: A new burst after the summary leaves
- **WHEN** a summary has auto-dismissed and a new push arrives afterwards
- **THEN** that push appears as its own notification with its own message, starting a new group
