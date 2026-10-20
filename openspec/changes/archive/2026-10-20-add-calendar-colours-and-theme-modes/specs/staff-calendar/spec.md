## MODIFIED Requirements

### Requirement: Events show schedule, status and visitor at a glance
Each event SHALL show:
- its scheduled time (or "Any time");
- the primary contact's name, plus "+N" when there are co-visitors;
- a status label and colour: Pending (submitted), Expected (approved),
  Inside (checked in), Visited (checked out), Missed (archived), Denied
  (denied);
- a visitor-category colour accent.

Every event, in Month, Week and Day views, SHALL be drawn filled with its
status colour: a tinted background with text in that status colour. The
colours SHALL be:

| Status | Colour |
|---|---|
| Pending | info |
| Expected | success |
| Inside | secondary accent |
| Visited | neutral |
| Missed | warning |
| Denied | danger |

The visitor-category colour SHALL remain visible as a solid left accent on
each event. A plain white or uncoloured event row SHALL NOT be used.

The status filter chips SHALL use the same fills, so they also act as the
colour legend.

In Month view, each day's visit count SHALL be shown with a tint whose
strength steps up with the day's total:
- none at 0;
- light at 1–4;
- medium at 5–14;
- strong at 15 or more.

Busier days are therefore distinguishable at a glance, on phones as well.

Day view and the event's hover or focus detail SHALL also show the
purpose, the actual check-in and check-out times when present (in the
tenant timezone), and, for `branch` scope, the host name ("Unassigned" when
null) and the branch.

Status SHALL be conveyed by text as well as colour: a visible label in Week
and Day views, and the accessible name in every view. Event text SHALL meet
4.5:1 contrast against its fill in both the light and dark themes.

#### Scenario: Checked-in visitor
- **WHEN** an event has status `checked_in` with a check-in time of 10:42
- **THEN** it shows "Inside" and Day view shows "Checked in 10:42"

#### Scenario: Group visit
- **WHEN** an event has a visitor count of 4
- **THEN** it shows the primary contact name followed by "+3"

#### Scenario: Month cell shows status fills
- **WHEN** a month cell contains one pending, one missed and one checked-out
  visit
- **THEN** the three events are filled blue, amber and grey respectively,
  each with its category accent on the left

#### Scenario: Filter chips double as the legend
- **WHEN** the calendar toolbar is shown
- **THEN** each enabled status chip is filled with the same colour its
  events use

#### Scenario: Busy day stands out
- **WHEN** one day has 20 visits and the next has 2
- **THEN** the first day's count shows the strong tint and the second shows
  the light tint

#### Scenario: Readable in dark mode
- **WHEN** the dark theme is active
- **THEN** every status-filled event's text meets 4.5:1 contrast against
  its fill
