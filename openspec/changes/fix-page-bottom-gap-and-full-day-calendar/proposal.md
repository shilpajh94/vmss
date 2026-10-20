## Why

Two problems staff hit in the portal:

- **Pages have no bottom gap.** When a page is taller than the screen,
  its last card ends flush against the bottom edge of the window. The
  shell's bottom padding is lost. The calendar's week board shows it most
  clearly: the board runs into the window edge, and the page scrolls by a
  few pixels, pushing the "Calendar" heading under the top bar.
- **The calendar only shows hours that have visits.** Week and Day views
  group visits under a heading for each hour that has visits ("10:00 AM",
  "2:00 PM"…). Empty hours are left out, so a day doesn't read as a day.
  Invitations can be scheduled at any hour, from 12:00 AM to 11:00 PM, and
  staff want to see the whole day laid out.

## What Changes

- **Every staff and admin page keeps a bottom gap.**
  - When a page scrolls, the space after its last element matches the
    page's side padding (16, 24 or 32px by width).
  - Fill-height layouts (the calendar week board, pages with a fixed
    header and a scrolling data region) end the same gap above the bottom
    edge. They do not make the page scroll.
- **Week and Day views show the full day, 12:00 AM to 11:00 PM.**
  - All 24 hour headings are shown in order, whether or not an hour has
    visits.
  - An hour with no visits is a compact row with just its heading, so a
    quiet day stays short.
  - "Any time" visits stay in their own group after 11:00 PM.
  - Per-day paging stays the same: hours later than the last loaded visit
    are not marked empty until the day is fully loaded.
  - When a column or the day list first opens, it scrolls to the first
    hour that has visits. A refresh does not move it.
- Month view is unchanged.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `app-shell`: adds a requirement that page content keeps a bottom gap
  equal to the page padding, both when the page scrolls and when a layout
  fills the height.
- `staff-calendar`: Week and Day views show all 24 hour slots from
  12:00 AM to 11:00 PM instead of only hours with visits. They open
  scrolled to the first busy hour.

## Impact

- **Shell:** `components/RouteTransition.tsx`, `components/AppShell.tsx`
  and `components/PageContentLayout.tsx` change how the bottom gap is
  produced. Only class changes; no new components.
- **Calendar:**
  - `components/calendar-grouping.ts` gains a full-day slot builder.
  - `PagedDayList.tsx` renders the 24-hour timeline and places the
    load-more sentinel at the loading frontier.
  - `WeekBoard.tsx` drops its hard-coded 24px bottom gap and uses the
    shared one.
  - `DayAgenda.tsx` scrolls to the first busy hour on open.
- **Tests:** e2e cases in `e2e/test_staff_calendar.py` for the 24-hour
  timeline, plus a bottom-gap check in `e2e/test_responsive_matrix.py`.
  The web repo has no unit-test runner.
- **API:** none. Uses the existing feed and day-page endpoints.
- **Dependencies:** none.
