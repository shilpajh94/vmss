## MODIFIED Requirements

### Requirement: Status filter, truncation and empty states
The page SHALL provide a status filter. By default it SHALL show every
status except Denied. Changing it SHALL refetch with the chosen statuses and
SHALL reset every column and the day list to their first page. Each week
column and the day list SHALL also return to the top of its scroll, so
the reset list doesn't immediately load past its first page.

No view SHALL drop visits: every visit of every day SHALL be reachable by
scrolling a week column or the day list. The page SHALL NOT show a "not
every visit is listed" banner.

A range with no events SHALL show an empty-state message rather than a
blank grid area. A day column with no visits SHALL show "No visits". A
failed request SHALL show the standard error state with a retry action. A
failed "load more" SHALL show a retry control inside that column or list
only.

#### Scenario: Showing denied visits
- **WHEN** the user adds "Denied" in the status filter
- **THEN** the feed is refetched including denied invitations, and they are
  shown with the "Denied" label

#### Scenario: Changing the filter after scrolling a column
- **WHEN** the user has scrolled Monday's week column far enough to load
  several pages, then turns a status in the filter on or off
- **THEN** Monday's column shows its top again and holds no more than the
  first page (plus the one preload a tall column makes on open)

#### Scenario: Truncated month
- **WHEN** a month has days with more visits than a month cell shows
- **THEN** no "not every visit is listed" banner appears, and each month
  cell's count still equals that day's `total`, with "+N more" opening the
  full, paged day

#### Scenario: Empty week
- **WHEN** the week has no visits
- **THEN** the week board shows an empty-state message

#### Scenario: Load-more failure is local
- **WHEN** loading the next page of Monday's column fails
- **THEN** Monday's column shows a retry control, and the other columns
  and the toolbar keep working
