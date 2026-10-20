## ADDED Requirements

### Requirement: Switching theme repaints in one clean step
Changing the theme (by choosing in the control, or by the device changing
while System is selected) SHALL repaint every themed surface in the same
frame. That includes page backgrounds, cards, buttons, chips, the top bar,
the calendar and the dashboard charts.

- No element SHALL fade its colours separately or recolour on a later
  frame.
- Layout SHALL NOT shift during a switch: no element moves or resizes.
- Where the browser supports view transitions and the user has not asked
  for reduced motion, the switch MAY play a single cross-fade of at most
  200ms over the whole page.
- Otherwise the switch SHALL be instant.
- Interactive transitions (hover, press, open/close) SHALL behave normally
  once the switch has finished.

#### Scenario: Charts change with everything else
- **WHEN** an admin on the dashboard switches from Light to Dark
- **THEN** in the first repainted frame the chart gridlines and axis text
  already use their dark colours, alongside the dark cards

#### Scenario: No staggered fades
- **WHEN** a user switches theme on the invitations board
- **THEN** buttons and cards whose colours normally transition on hover
  reach their new colours immediately, not over 100–180ms

#### Scenario: Reduced motion
- **WHEN** the device requests reduced motion and the user switches theme
- **THEN** the switch is instant with no cross-fade

#### Scenario: Menu does not overlap the switch
- **WHEN** the user picks Dark in the theme menu
- **THEN** the menu is gone by the repainted frame, and no closing
  animation plays over the recolouring page

#### Scenario: Hover transitions still work afterwards
- **WHEN** the switch has finished and the user hovers a button
- **THEN** its hover colour transitions as before
