## ADDED Requirements

### Requirement: A Failing Automatic Refresh Is Reported Once, Not on Every Attempt
When an automatic background refresh fails, the page SHALL keep showing its
last good data and SHALL indicate a "retrying" state on its refresh
control. It SHALL NOT show an error toast for each failed attempt. An error
toast or error state SHALL be shown only for a failed initial load or a
failed manual refresh. When a later automatic refresh succeeds, the
"retrying" indication SHALL clear.

#### Scenario: API down while a list page is open
- **WHEN** an admin list page is open and the API stops responding for one
  minute
- **THEN** no error toasts appear during that minute, the last good rows
  stay visible, and the refresh control shows that it is retrying

#### Scenario: API recovers
- **WHEN** the next automatic refresh after an outage succeeds
- **THEN** the data updates and the retrying indication disappears

### Requirement: Automatic Refresh Re-Fetches Only the Page's Changing Data
An automatic refresh SHALL re-fetch only the records the page displays (list
rows, board columns, dashboard metrics). It SHALL NOT re-fetch the current
user, role lists, host or employee lists, or filter option lists on each
interval. Those load once per page visit (or come from shared app context)
and refresh on a manual refresh.

#### Scenario: Ten-second tick on the Buildings page
- **WHEN** the Buildings page refreshes automatically
- **THEN** only the building listing request is sent; the current-user and
  branch-option requests are not repeated

#### Scenario: Board refresh
- **WHEN** the invitations board refreshes automatically
- **THEN** only its column listings are requested, with no per-card detail
  requests
