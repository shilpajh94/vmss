## MODIFIED Requirements

### Requirement: Animations use one shared timing scale
The system SHALL draw every UI animation's duration and easing from one
shared, named scale. The scale SHALL have a short step for micro-feedback
(hover or press, no longer than 120ms), a standard step for overlays and
panels (150–220ms), and a long step for route and step transitions (no
longer than 300ms). No UI animation SHALL run longer than 300ms, with
two exceptions: progress indicators that loop for as long as an operation
is in flight, and the notification bell's new-notification ring. The ring
is an attention cue, not a state transition. It SHALL take its duration
from its own named token, SHALL run no longer than 800ms, and SHALL play
once per trigger, never looping.

#### Scenario: Two different overlays open
- **WHEN** a user opens a modal dialog and, separately, the notification
  popover
- **THEN** both play their enter animation with the same standard duration
  and easing

#### Scenario: No animation drags
- **WHEN** any non-looping UI animation other than the new-notification
  bell ring plays
- **THEN** it completes within 300ms

#### Scenario: The bell ring stays bounded
- **WHEN** the notification bell rings for a new notification
- **THEN** the ring completes within 800ms and does not repeat
