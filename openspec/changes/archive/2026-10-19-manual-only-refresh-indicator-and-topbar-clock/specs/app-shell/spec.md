## MODIFIED Requirements

### Requirement: Top bar compacts on small screens
Below 768px viewport width, the top bar SHALL keep the menu button, the page's breadcrumb or title, which truncates with an ellipsis, and the notification bell and user menu. It SHALL hide the page description text and the top-bar clock, and the refresh control SHALL remain as an icon button. The top bar SHALL NOT wrap to more than one line.

#### Scenario: Top bar at phone width
- **WHEN** any staff or admin page is viewed at 360px wide
- **THEN** the top bar is a single row with the menu button, a truncated title, and the bell/user controls, and nothing overflows its right edge

## ADDED Requirements

### Requirement: The top bar shows a live clock
From 768px viewport width up, the admin and staff top bars SHALL show the
current local time of the user's device in 24-hour `HH:MM:SS` format,
for example `14:05:09`. It SHALL sit beside the refresh control. The
clock SHALL tick once per second, stay in step with the device clock,
and keep a fixed width so its digits changing never shifts the controls
beside it. Assistive technology SHALL NOT announce each tick. Below 768px
the clock SHALL be hidden (see "Top bar compacts on small screens").

#### Scenario: Clock on a desktop top bar
- **WHEN** an admin or staff member views any page at 1440px wide at
  2:05:09 pm local time
- **THEN** the top bar shows `14:05:09`, and one second later `14:05:10`

#### Scenario: Leading zeros
- **WHEN** the local time is 9:03:07 am
- **THEN** the clock shows `09:03:07`

#### Scenario: Clock hidden on phones
- **WHEN** a page is viewed at 360px wide
- **THEN** no clock is shown, and the top bar stays one row without
  overflowing
