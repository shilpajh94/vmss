## ADDED Requirements

### Requirement: The notification bell always shows the exact unread count
The notification bell in the shared top bar (admin, staff, and reception)
SHALL always show an unread badge with the exact number of unread
notifications the server reports. The badge SHALL NOT be capped or
abbreviated (no "9+"). When the count is zero, the badge SHALL show "0"
in a muted, neutral style that does not use the alert colour. When the
count is above zero, it SHALL use the alert colour. The badge SHALL widen
to fit its digits. At every supported viewport width, its digits SHALL
stay fully visible, the bell icon SHALL stay recognisable, and the top
bar SHALL NOT wrap or overflow. The bell's accessible name
SHALL state the count in every case, for example "Notifications, 0
unread" or "Notifications, 143 unread". Reading one notification or using
"Mark all read" SHALL update the badge immediately.

#### Scenario: Everything is read
- **WHEN** a signed-in staff member has no unread notifications
- **THEN** the bell shows a muted "0" badge, and its accessible name is
  "Notifications, 0 unread"

#### Scenario: More than nine unread
- **WHEN** a staff member has 12 unread notifications
- **THEN** the badge shows "12", not "9+", in the alert colour

#### Scenario: A large count still fits
- **WHEN** a staff member has 143 unread notifications and views the top
  bar at 360px wide
- **THEN** the badge shows "143" in full, and the top bar stays on one
  line with nothing overflowing

#### Scenario: Mark all read drops the badge to zero
- **WHEN** a staff member with unread notifications activates "Mark all
  read"
- **THEN** the badge changes to a muted "0" straight away

### Requirement: The notification bell rings when a new notification arrives
The system SHALL play a single ring animation on the bell, about 700ms
long, whenever a refresh of the notification feed returns at least one
notification the bell had not yet seen in this session. That refresh may
come from the background poll, a foreground push message, or the tab
becoming visible again. The first feed load after sign-in SHALL NOT ring,
and neither SHALL a refresh that returns no unseen notification. Several
new notifications arriving in one refresh SHALL produce one ring, not one
per notification. A ring that is triggered while one is still playing
SHALL restart it rather than queueing a second. When the user's system
requests reduced motion, the bell SHALL NOT move; the updated badge still
shows.

#### Scenario: A new notification arrives while the page is open
- **WHEN** a staff member is on any page and the next poll returns a
  notification they had not seen
- **THEN** the bell rings once and the badge shows the new unread count

#### Scenario: Signing in does not ring
- **WHEN** a staff member signs in and already has unread notifications
- **THEN** the badge shows the count and the bell does not ring

#### Scenario: Nothing new
- **WHEN** a background poll returns only notifications already seen
- **THEN** the bell does not ring

#### Scenario: Reduced motion
- **WHEN** reduced motion is requested and a new notification arrives
- **THEN** the bell does not animate, and the badge shows the new count
