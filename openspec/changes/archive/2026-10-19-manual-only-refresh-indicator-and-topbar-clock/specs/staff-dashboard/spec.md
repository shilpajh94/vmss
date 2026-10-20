## MODIFIED Requirements

### Requirement: Refresh reloads the visit-requests list
The system SHALL present exactly one refresh control on the staff Invitations page: the shared refresh control in the staff top bar, as on the admin top bar, with no last-updated label beside it. The page SHALL NOT render its own Refresh button. When that control is activated, the system SHALL re-fetch, for every column, the pages that column has already loaded, and re-render the board with the latest data. A column the staff member has scrolled into SHALL keep its loaded depth and scroll position.

#### Scenario: Only one refresh control is shown
- **WHEN** the dashboard finishes loading
- **THEN** exactly one refresh control is visible on the page, in the top bar, with no "Updated …" label beside it

#### Scenario: Staff refreshes the board
- **WHEN** a staff member activates the refresh control
- **THEN** the system re-fetches every column's loaded pages and updates the board with the result

#### Scenario: Refresh keeps a scrolled column's depth
- **WHEN** a staff member has loaded 60 cards into the Requested column, scrolled down, and activates the refresh control
- **THEN** the Requested column still holds up to 60 cards after the refresh and is not scrolled back to the top
