## ADDED Requirements

### Requirement: The notification bell repeats its ring while notifications stay unread
While the unread count is above zero and the tab is visible, the
notification bell SHALL play its ring again every 30 seconds as a
reminder. This is the same single ring used for a new arrival. The first
reminder SHALL come 30 seconds after the page loads or after the most
recent ring, whichever is later, so a new-arrival ring restarts the
30-second wait. The bell SHALL stop reminding as soon as the unread count
reaches zero, SHALL NOT remind while its notification popover is open,
and SHALL NOT remind while the tab is hidden. With reduced motion
requested, the bell SHALL NOT move.

#### Scenario: Unread notifications left alone
- **WHEN** a staff member has 3 unread notifications and leaves the page
  open and visible
- **THEN** the bell rings once every 30 seconds

#### Scenario: Reading everything stops the reminder
- **WHEN** the staff member activates "Mark all read"
- **THEN** the bell stops ringing, and the badge shows "0"

#### Scenario: A new arrival restarts the wait
- **WHEN** a new notification makes the bell ring 20 seconds after the
  last reminder
- **THEN** the next reminder comes 30 seconds after that new-arrival
  ring, not 10 seconds later

#### Scenario: Popover open or tab hidden
- **WHEN** the notification popover is open, or the tab is in the
  background
- **THEN** no reminder ring plays until it is closed or the tab is visible
  again

#### Scenario: Nothing unread
- **WHEN** a staff member has no unread notifications
- **THEN** the bell never rings as a reminder
