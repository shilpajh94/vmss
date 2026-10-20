## Why

The full-day timeline (`fix-page-bottom-gap-and-full-day-calendar`)
shows all 24 hours. Most of them are empty night hours that push the
working day down each column. Visits are almost always within working
hours (9 AM–6 PM).

The week view also looks crowded:
- With the sidebar open at 1280–1440px, seven columns are only about
  130–170px wide.
- Each card spends three lines on name, "● Pending 10:00 AM" and host.
- Every column shows a scrollbar.
- Full-width hour bars and tight gaps leave little white space.

## What Changes

- **Working-hours timeline.** Week columns and Day view always show the
  hours from 9:00 AM to 6:00 PM (10 headings).
  - Earlier or later hours appear only when they have visits.
  - "Any time" stays last.
  - A column opens at its top, so the auto-scroll to the first busy hour
    is removed.
- **Roomier week board.**
  - **Columns per screen:** five from 1280px, all seven from 1536px. The
    board opens scrolled so today is visible.
  - **Two-line cards:** the name, then the time and (for branch-wide
    viewers) the host. In Week view, status is shown by the card's fill
    and dot. The status word stays in the tooltip, the accessible name and
    Day view.
  - **Lighter visuals:**
    - a compact one-row column header with the day's count as a pill;
    - hour headings as a small label on a hairline rule, not a filled bar;
    - more padding and gaps;
    - thin scrollbars that appear only on hover or while scrolling.
- Month view is unchanged. Day view only gets the working-hours window.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `staff-calendar`:
  - "Month, week and day views with date navigation" is replaced by
    "Month, week and day views with a working-hours timeline". Views,
    navigation and paging are unchanged. The full-day timeline becomes the
    working-hours timeline, and opening at the first busy hour is removed.
  - "Events show schedule, status and visitor at a glance": a visible
    status label is required in Day view only. Week cards use two lines.
  - "Calendar is usable on small screens": five columns from 1280px,
    seven from 1536px, and the board opens at today.

## Impact

- **Calendar UI:**
  - `pages/calendar/components/calendar-grouping.ts`: `buildDayTimeline`
    gets the working-hours window.
  - `PagedDayList.tsx`: hour heading style; the open-at-first-busy-hour
    effect and the `resetKey` prop are removed.
  - `CalendarEventChip.tsx`: two-line `block` variant.
  - `WeekBoard.tsx`: column widths, header, spacing, scrollbars, and
    opening at today.
  - `DayAgenda.tsx` and `use-day-pages.ts`: `eventsKey` is dropped if
    nothing else uses it.
- **Tests:** `e2e/test_staff_calendar.py` timeline, auto-scroll and
  columns-per-screen tests are updated. The device-width test that runs
  over every route is unaffected.
- **API and dependencies:** none.
- **Sequencing:** this builds on `fix-page-bottom-gap-and-full-day-calendar`.
  Archive that change first.
