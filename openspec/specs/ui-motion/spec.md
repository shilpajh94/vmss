# ui-motion Specification

## Purpose

The ui-motion capability defines how the interface moves: shared motion
timing, enter and exit animation for every overlay and collapsible region,
in-progress feedback on action controls, and the reduced-motion rule that
applies to all of them. Together these keep state changes smooth instead
of abrupt.

## Requirements

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

### Requirement: Reduced-motion preference is honoured everywhere
The system SHALL, when the user's operating system or browser requests
reduced motion, disable every movement-based animation. This includes
slides, scales, collapses, route transitions, step transitions, and
skeleton shimmer. Any opacity fade that remains SHALL complete within
100ms. The final state SHALL be the same as with motion enabled, and no
content or control SHALL become unreachable because an animation was
skipped.

#### Scenario: Opening a dialog with reduced motion
- **WHEN** reduced motion is requested and the user opens a modal dialog
- **THEN** the dialog appears without scaling or sliding, and is fully
  interactive at once

#### Scenario: Skeletons with reduced motion
- **WHEN** reduced motion is requested and a page shows skeleton
  placeholders
- **THEN** the placeholders render as static blocks without a shimmer
  animation

### Requirement: Modal dialogs and sheets animate in and out
The system SHALL animate every modal dialog, confirmation dialog, and
bottom sheet when it opens and when it closes, instead of making it appear
or disappear instantly. On open, the backdrop SHALL fade in and the panel
SHALL fade in while scaling up slightly from its final position. Below the
small-screen breakpoint, where the panel is a bottom sheet, the panel SHALL
slide up from the bottom edge instead. On close, the system SHALL play the
reverse animation, and SHALL remove the dialog from the page only after
that animation finishes. While the dialog is closing it SHALL NOT accept
input, and focus SHALL return to the control that opened it.

#### Scenario: Opening a confirmation dialog on desktop
- **WHEN** an admin clicks Delete on a branch at 1280px wide
- **THEN** the backdrop fades in and the confirmation panel fades and
  scales into the centre of the screen

#### Scenario: Opening a dialog on a phone
- **WHEN** a user opens any modal at 375px wide
- **THEN** the panel slides up from the bottom edge as a sheet while the
  backdrop fades in

#### Scenario: Closing a dialog
- **WHEN** the user cancels, confirms, presses Escape, or taps the backdrop
  of an open dialog
- **THEN** the panel and backdrop animate out, the dialog is removed only
  after the animation ends, and focus returns to the control that opened it

#### Scenario: Reopening during the exit animation
- **WHEN** the user re-triggers a dialog while its exit animation is still
  playing
- **THEN** the dialog returns to its fully open state without flickering or
  showing two copies

### Requirement: Popovers and menus animate from their anchor
The system SHALL animate every anchored floating surface when it opens and
closes. This includes the notification popover, the user menu,
autocomplete suggestion lists, and dropdown menus. Each SHALL fade and
scale slightly from the edge nearest its trigger, and SHALL be removed
only after its exit animation ends.

#### Scenario: Opening the notification popover
- **WHEN** a staff user activates the notification bell
- **THEN** the popover fades and scales in from the bell's side rather than
  appearing instantly

#### Scenario: Autocomplete suggestions appear
- **WHEN** a user types enough characters for autocomplete suggestions to
  show
- **THEN** the suggestion list fades in beneath the field, and fades out
  when dismissed

### Requirement: Toasts animate in and out
The system SHALL animate each toast notification in when it appears and
out when it is dismissed or expires. The toast SHALL slide in from the
viewport edge it is anchored to and fade out on exit. When a toast leaves,
the remaining toasts SHALL move smoothly into the freed space instead of
jumping into it. When a grouped push summary's count changes, the toast
SHALL stay in place and only its text SHALL change, with no re-entry
animation.

#### Scenario: A success toast appears
- **WHEN** a mutation succeeds and the system shows a success toast
- **THEN** the toast slides in from the right edge into the bottom-right
  corner on desktop, or up from the bottom edge on a phone

#### Scenario: One of several toasts is dismissed
- **WHEN** three toasts are stacked and the user dismisses one of them
- **THEN** it fades out and the remaining two glide into its place

#### Scenario: A summary's count changes
- **WHEN** a "3 new notifications" summary is showing and another push
  arrives
- **THEN** the text changes to "4 new notifications" without the toast
  sliding out and back in

### Requirement: Collapsible regions expand and collapse smoothly
The system SHALL animate the height and opacity of any region that a user
shows or hides in place, instead of inserting or removing it all at once.
This covers filter panels, expandable text, and sections that can be
collapsed. While the region expands or collapses, the content below it
SHALL move with it continuously rather than jumping to its new position.

#### Scenario: Opening a filter panel
- **WHEN** an admin activates "Filters" on a list page
- **THEN** the filter panel expands from zero height to its full height
  while fading in, and the table below moves down with it

#### Scenario: Closing a filter panel
- **WHEN** the admin activates "Filters" again
- **THEN** the panel collapses smoothly and the table moves back up with it

### Requirement: The navigation drawer slides in and out
The system SHALL, below desktop width, slide the sidebar drawer in from
the left edge while its backdrop fades in when the drawer opens. When the
drawer closes, the system SHALL slide it back out and fade the backdrop
before hiding it.

#### Scenario: Closing the drawer by navigating
- **WHEN** the drawer is open at 375px and the user taps a navigation item
- **THEN** the drawer slides out to the left while the new page's content
  transitions in

### Requirement: Action buttons show pending feedback while their action runs
The system SHALL give in-progress feedback on any button that starts an
asynchronous action, such as Save, Create, Delete, Approve, Deny, Check
in, Check out, Export, or Send. While the action runs, the button SHALL
show an inline spinner beside or in place of its icon. It SHALL keep its
rendered width so neighbouring controls do not shift. It SHALL be disabled
so the action cannot be submitted twice, and it SHALL expose a busy state
to assistive technology. When the action settles, whether it succeeds or
fails, the button SHALL return to its normal state.

#### Scenario: Saving a form
- **WHEN** an admin clicks Save in an edit dialog
- **THEN** the Save button shows a spinner, stays the same width, and does
  nothing if clicked again until the save finishes

#### Scenario: Action fails
- **WHEN** a pending action fails
- **THEN** the button returns to its normal, enabled state, and the failure
  is reported through the existing error toast

### Requirement: Interactive controls give immediate visual feedback
The system SHALL give every clickable control a visible hover and pressed
or active state that transitions smoothly using the shared short timing
step. This covers buttons, icon buttons, navigation items, cards that open
details, table row actions, toggles, and segmented controls. A control's
state change SHALL NOT alter its size or the layout around it.

#### Scenario: Pressing a primary button
- **WHEN** the user presses and releases a primary button
- **THEN** the button shows a brief pressed state, and the controls around
  it do not move

#### Scenario: Toggling a switch
- **WHEN** the user activates a toggle switch or segmented control
- **THEN** the thumb or selected indicator glides to its new position
  instead of snapping

### Requirement: The refresh control's icon accelerates, spins and settles
The system SHALL animate the top-bar refresh icon for a user-started
refresh in three phases: it SHALL ease into its rotation rather than
starting at full speed, turn at a steady speed while the refresh runs, and
when the refresh finishes SHALL ease out to rest at its upright position,
completing its current turn rather than stopping abruptly or snapping
back. The settle SHALL take no longer than one standard motion duration
beyond completing the current turn. Activating the control again while the
icon is settling SHALL resume the steady spin from the icon's current
angle without a jump. While idle, hovering or focusing the control SHALL
nudge the icon a small fraction of a turn as an affordance, returning when
the pointer or focus leaves. When reduced motion is requested, the icon
SHALL spin at a constant speed while the refresh runs, SHALL stop upright
without easing when it finishes, and SHALL NOT perform the hover nudge.

#### Scenario: Starting a refresh
- **WHEN** the user clicks the refresh control
- **THEN** the icon begins turning slowly and builds up to a steady spin,
  rather than jumping to full speed

#### Scenario: Refresh finishes
- **WHEN** the page's re-fetch completes while the icon is spinning
- **THEN** the icon slows and comes to rest upright, with no visible snap
  or jump in angle

#### Scenario: Clicking again while it settles
- **WHEN** the icon is easing to a stop and the user clicks the control
  again
- **THEN** the icon picks up its steady spin from where it is, without
  jumping back to upright first

#### Scenario: Hover affordance
- **WHEN** the refresh control is idle and the user hovers it
- **THEN** the icon turns slightly, and turns back when the pointer leaves

#### Scenario: Refresh with reduced motion
- **WHEN** reduced motion is requested and the user starts a refresh
- **THEN** the icon spins at a constant speed until the refresh finishes,
  then shows upright immediately, and hovering produces no rotation
