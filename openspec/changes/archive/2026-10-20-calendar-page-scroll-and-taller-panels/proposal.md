## Why

`fix-paging-footers-and-calendar-day-scroll` made the Week board and the
Day card fit the space left under the page title and toolbar, so the page
itself never scrolls. That fixed the cut-off columns, but it left the
panels cramped: the title and toolbar take about 300px. At 1280×720 the
board is only about 360px tall, enough for roughly four visits per
column, and Day view's card is the same.

Staff would rather scroll the page to get a full-height board. The
title and toolbar scroll away, and the visits then fill the screen. Each
column and the Day card still scroll on their own.

## What Changes

- **The calendar page scrolls again in Week and Day views.**
  - The Week board and the Day card are as tall as the visible page area:
    the window height under the top bar, less the page's top padding and
    bottom gap. They no longer fit to the space left under the toolbar.
  - With the page scrolled down, the panel fills the screen. Scrolled to
    the top, the title and toolbar are back and the panel continues below
    them.
  - Their height no longer changes when the toolbar wraps.
- **Each panel keeps its own scroll.**
  - Week columns and the Day card's timeline still scroll on their own,
    with their fixed headers and paging footers.
  - Lazy loading still follows each panel's own scroll.
- **Scrolling hands over between the panel and the page.**
  - When a column or the Day card's body reaches its top or bottom, a
    further wheel or swipe scrolls the page. The user can't get stuck
    inside a full-height panel.
  - Today the bodies block this (`overscroll-contain`).
  - The Week board keeps blocking sideways hand-over, so swiping between
    days doesn't trigger browser back/forward.
- **The minimum panel height goes back to 420px** at every width. The
  240px floor only existed to avoid page scrolling.
- Day view on phones is unchanged: it still grows with its content and
  scrolls with the page. The Week board on phones gets the same
  visible-height sizing as on desktop.
- Month view, list pages and the paging footers are unchanged.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `staff-calendar`:
  - "Day view scrolls its timeline inside its own panel": the card is as
    tall as the visible page, and the page scrolls to reach it. It no
    longer fits under the toolbar without page scroll.
  - "Week board fits short desktop windows" is replaced by "Week board and
    Day card are as tall as the visible page", which also covers scroll
    hand-over to the page.

## Impact

- **Calendar UI:**
  - `pages/calendar/hooks/use-fill-height.ts`: the measurement no longer
    depends on the element's top, and the toolbar observer is removed.
  - `calendar-page.tsx`: the `controlsRef` wrapper and `remeasureKey` are
    no longer needed.
  - `WeekBoard.tsx`: floor and overscroll changes.
  - `DayAgenda.tsx`: floor and overscroll changes.
- **Tests** (from the previous change):
  - `e2e/test_staff_calendar.py`: the "page does not scroll" assertions
    become "panel is as tall as the visible page and scroll hands over to
    the page".
  - `e2e/test_responsive_matrix.py`: the Week/Day "main does not scroll"
    check is removed.
- **API and dependencies:** none.
- **Sequencing:** this modifies requirements added by
  `fix-paging-footers-and-calendar-day-scroll`. Archive that change first.
