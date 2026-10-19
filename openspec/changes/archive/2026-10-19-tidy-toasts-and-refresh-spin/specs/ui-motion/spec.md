## MODIFIED Requirements

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

## ADDED Requirements

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
