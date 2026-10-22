## MODIFIED Requirements

### Requirement: A shared loading indicator represents in-progress async operations
The system SHALL, while a view's first data-fetching operation is in
progress and before any data has loaded for it, render a skeleton
placeholder in place of that view's content. The skeleton SHALL be shaped
like the content it stands in for: table rows for tables, cards for boards
and card grids, tiles for KPI rows and chart cards, and label-and-field
rows for forms and settings. It SHALL occupy approximately the same space,
so the layout does not visibly shift when the real content replaces it. The
system SHALL remove the skeleton once that first operation completes,
whether it succeeds or fails. A small, self-contained region with no
meaningful layout to preview, such as a modal body that fetches on open,
SHALL use the shared spinner-and-label indicator instead.

#### Scenario: Operation in progress
- **WHEN** a view's first data-fetching operation has started and not yet
  completed
- **THEN** the system shows a skeleton placeholder, shaped like the view's
  content, in place of that content

#### Scenario: Operation completes
- **WHEN** a view's first data-fetching operation completes, successfully
  or not
- **THEN** the system removes the skeleton placeholder

#### Scenario: Content replaces a table skeleton without shifting layout
- **WHEN** a list page's first load completes and its table replaces the
  table-row skeleton
- **THEN** the page heading, filter controls, and pagination stay where
  they were while the skeleton was showing

#### Scenario: Content fades in over its skeleton
- **WHEN** real content replaces a skeleton placeholder
- **THEN** the content fades in rather than appearing instantly

## ADDED Requirements

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
- **WHEN** the 15-second automatic refresh runs
- **THEN** no progress bar, dimming, or skeleton appears, and changed data
  updates in place

#### Scenario: Result set becomes empty
- **WHEN** a re-fetch triggered by a filter returns zero items
- **THEN** the stale rows are replaced by the shared empty-state component
  in the same region, without first collapsing to a spinner

### Requirement: Out-of-order responses never overwrite newer results
The system SHALL, when several re-fetches of the same view overlap (for
example, quick successive filter changes or typing in a search), display
only the result of the most recently issued request. It SHALL ignore any
earlier response that arrives after it, and SHALL keep showing the
in-progress cue until that most recent request settles.

#### Scenario: Two filter changes in quick succession
- **WHEN** a user selects "Active" and then, before the first response
  returns, selects "Inactive"
- **THEN** the view ends up showing the "Inactive" results even if the
  "Active" response arrives last

### Requirement: A failed re-fetch keeps the last good content
The system SHALL, when a re-fetch fails for a view that already shows data,
keep the last successfully loaded content on screen. It SHALL remove the
in-progress cue and report the failure through an error toast, rather than
replacing the content with the full-region error state. The full-region
error state with a retry action SHALL be used only when the first load
fails and there is no content to keep.

#### Scenario: Filter change fails
- **WHEN** a filter change triggers a re-fetch that fails
- **THEN** the previous rows remain visible, the progress bar disappears,
  and an error toast explains the failure

#### Scenario: First load fails
- **WHEN** a view's first data-fetching operation fails
- **THEN** the view shows its error state with a retry action in place of
  the skeleton
