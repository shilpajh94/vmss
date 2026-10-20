## Why

The full e2e pass (`npm run e2e`, 2026-10-20) ends with 16 failed, 129
passed, 2 xfailed, so `calendar-page-scroll-and-taller-panels` task 3.7 and
any later layout change can't be signed off. Two of the failures are real
product bugs: the bottom gap is gone below 1024px, and a column stays
scrolled down after the status filter changes. The others are tests that
depend on today's date, on data left by earlier runs, or on timing.

## What Changes

- **Bottom gap below 1024px (12 failures, `test_every_route_fits` at
  320–820px, both themes):** the route wrapper's trailing spacer is 0px tall
  below 64rem. Chromium leaves a zero-height box out of the scrollable
  area, so the section gap in front of it can't be reached and every
  scrolled page ends flush with the bottom edge (`endGap` 0–1px against
  16/24px). Give the spacer a real height at every width, keeping the
  total gap at 16/24/32px.
- **Status filter leaves a column scrolled down
  (`test_status_filter_resets_columns`):** changing the filter resets a
  week column to its first page, but the column body keeps its old
  `scrollTop`. Its last card is then near the bottom edge, so the column
  immediately preloads past the first page (40 loaded where 20 is
  expected). A new day, branch or filter should start the column (and the
  Day list) at the top.
- **Week tests that assume Monday is on screen
  (`test_week_column_status_is_in_view_without_scrolling`):** at the e2e
  width (1440px, 5 columns) the board opens at today's column. Today
  (Tue 2026-10-20) is in the test week, so Monday 19 Oct is scrolled out of
  view sideways. The test must bring the column it checks into view rather
  than rely on the date it happens to run on.
- **Timeline week test that depends on seeded data
  (`test_week_column_shows_working_hours_and_busy_out_of_hours`):** each
  run adds two visits to 2026-12-02. With the visits from earlier runs, the
  23:15 visit is now past the column's first page of 10. The test must load
  the column to the end before looking for it.
- **Lifecycle race (`test_staff_invitation_lifecycle`):** the test reads
  the invitation's status through the API before the approver's "Approve
  Request" call has finished. It passes when run alone. Wait for the dialog
  to close first.
- Then rerun lint, build and the full e2e pass until all of it is green,
  and close `calendar-page-scroll-and-taller-panels` task 3.7.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-calendar`: "Status filter, truncation and empty states". Changing
  the filter also brings each week column and the day list back to the top.
  (`app-shell` "Page content keeps a bottom gap" is unchanged; the fix
  restores behaviour the spec already requires.)

## Impact

- `src/styles/theme.css` (`h-page-end-gap`), possibly `RouteTransition.tsx`.
- `src/presentation/pages/calendar/components/WeekBoard.tsx` and
  `DayAgenda.tsx` (reset scroll when the day/branch/filter key changes).
- `e2e/test_staff_calendar.py`, `e2e/test_invitation_lifecycle.py`.
- No API changes. No new dependencies.
