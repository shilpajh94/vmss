## MODIFIED Requirements

### Requirement: Re-fetching keeps existing content visible
The system SHALL, when a view that has already loaded data re-fetches it,
keep the current content rendered in place for the whole re-fetch instead
of replacing it with a skeleton, spinner, or empty region. This covers a
filter change, search, sort, page change, date-range change, manual
refresh, retry after a mutation, or automatic poll. During a user-initiated
re-fetch, the system SHALL show an in-progress cue on that view's data
region, consisting of a thin indeterminate progress bar along the region's
top edge and reduced emphasis on the stale content. The view SHALL stay
scrollable and readable. When the new data arrives, the system SHALL swap
it in place and remove the cue. An automatic background poll SHALL NOT
show the cue.

#### Scenario: Changing a filter
- **WHEN** an admin changes the Status filter on a list page that has
  already shown results
- **THEN** the current rows stay on screen, slightly dimmed, with a thin
  progress bar above them, and are replaced by the filtered rows when the
  response arrives, with no height collapse in between

#### Scenario: Paging forward
- **WHEN** a user moves to the next page of a paginated list
- **THEN** the current page's rows stay visible with the in-progress cue
  until the next page's rows replace them, and the pagination control does
  not move

#### Scenario: Changing a dashboard date range
- **WHEN** a user switches a dashboard chart's range toggle
- **THEN** the existing chart stays visible with the in-progress cue until
  the new series replaces it

#### Scenario: Background poll
- **WHEN** the 10-second automatic refresh runs
- **THEN** no progress bar, dimming, or skeleton appears, and changed data
  updates in place

#### Scenario: Result set becomes empty
- **WHEN** a re-fetch triggered by a filter returns zero items
- **THEN** the stale rows are replaced by the shared empty-state component
  in the same region, without first collapsing to a spinner

