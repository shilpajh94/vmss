## MODIFIED Requirements

### Requirement: The notification bell rings when a new notification arrives
The system SHALL play a single ring animation on the bell, about 700ms
long, whenever a refresh of the notification feed returns at least one
notification the bell had not yet seen in this session. That refresh may
come from the background poll, a foreground push message, or the tab
becoming visible again. The first feed load after sign-in SHALL NOT ring,
and neither SHALL a refresh that returns no unseen notification. Several
new notifications arriving in one refresh SHALL produce one ring, not one
per notification. The bell SHALL NOT ring if, after that refresh, the
unread count is zero (for example, the new notification was already read
in another tab): with nothing unread there is no animation at all. A ring
that is triggered while one is still playing
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

#### Scenario: A new but already-read notification does not ring
- **WHEN** a refresh brings in a notification the bell had not seen, but
  it is already read and the unread count is 0
- **THEN** the bell does not ring, and the badge shows "0"

#### Scenario: Reduced motion
- **WHEN** reduced motion is requested and a new notification arrives
- **THEN** the bell does not animate, and the badge shows the new count

### Requirement: The notification bell repeats its ring while notifications stay unread
While the unread count is above zero and the tab is visible, the
notification bell SHALL play its ring again every 15 seconds as a
reminder. This is the same single ring used for a new arrival. The first
reminder SHALL come 15 seconds after the page loads or after the most
recent ring, whichever is later, so a new-arrival ring restarts the
15-second wait. The bell SHALL stop reminding as soon as the unread count
reaches zero, SHALL NOT remind while its notification popover is open,
and SHALL NOT remind while the tab is hidden. With reduced motion
requested, the bell SHALL NOT move.

#### Scenario: Unread notifications left alone
- **WHEN** a staff member has 3 unread notifications and leaves the page
  open and visible
- **THEN** the bell rings once every 15 seconds

#### Scenario: Reading everything stops the reminder
- **WHEN** the staff member activates "Mark all read"
- **THEN** the bell stops ringing, and the badge shows "0"

#### Scenario: A new arrival restarts the wait
- **WHEN** a new notification makes the bell ring 10 seconds after the
  last reminder
- **THEN** the next reminder comes 15 seconds after that new-arrival
  ring, not 5 seconds later

#### Scenario: Popover open or tab hidden
- **WHEN** the notification popover is open, or the tab is in the
  background
- **THEN** no reminder ring plays until it is closed or the tab is visible
  again

#### Scenario: Nothing unread
- **WHEN** a staff member has no unread notifications
- **THEN** the bell never animates, neither as a reminder nor for a
  refresh
