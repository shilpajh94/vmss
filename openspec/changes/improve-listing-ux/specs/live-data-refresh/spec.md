## MODIFIED Requirements

### Requirement: A manual refresh control remains available alongside automatic refresh
The system SHALL provide exactly one manual refresh control, shown in the admin top bar next to the notification bell icon, letting the user force an immediate re-fetch of the current operational list or dashboard page's data independent of the 15-second automatic interval. Individual list/dashboard pages SHALL NOT render their own separate refresh button. While a refresh (automatic or manual) is in flight, the shared control SHALL show a spinning animation, and once it completes the control SHALL show, immediately beside it, a "last updated" label reflecting when that page's data was last successfully refreshed.

#### Scenario: User forces an immediate refresh
- **WHEN** the user activates the shared top-bar refresh control
- **THEN** the system re-fetches the current page's data immediately, without waiting for the next automatic interval

#### Scenario: Refresh control animates while in flight
- **WHEN** a refresh (automatic or manually triggered) is currently in progress
- **THEN** the shared refresh control shows a spinning animation, and the animation stops as soon as that refresh completes or fails

#### Scenario: Last-updated label reflects the most recent successful refresh
- **WHEN** a refresh completes successfully
- **THEN** the label beside the refresh control updates to reflect that refresh's completion time

#### Scenario: Navigating to a different page updates what the control refreshes
- **WHEN** the user navigates from one operational list/dashboard page to another
- **THEN** the shared top-bar refresh control's manual-refresh action and "last updated" label apply to the newly active page's data, not the page navigated away from

#### Scenario: A page with no automatic refresh does not show a stale label
- **WHEN** the active page is not an operational list or dashboard page with automatic refresh enabled
- **THEN** the shared refresh control's "last updated" label does not display a value left over from a previously visited page
