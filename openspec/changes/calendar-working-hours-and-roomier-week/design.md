## Context

Builds on `fix-page-bottom-gap-and-full-day-calendar`:
- `buildDayTimeline(events, complete)` returns 24 hour slots plus
  "Any time", and a `frontier` index for the loading row.
- `PagedDayList` renders those slots and scrolls to the first busy hour
  once per `resetKey`.
- `WeekBoard` sizes columns `w-full sm:w-1/2 md:w-1/3 xl:w-[calc(100%/7)]`.
  Each column has a three-line header button and an
  `overflow-y-auto` body.
- `CalendarEventChip`'s `block` variant takes three lines: name, then
  dot + status + time, then host.

See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Keep the working day at the top of every column without hiding any
  visit.
- Make a seven-day week readable on a 1280–1440px laptop with the
  sidebar open.

**Non-Goals:**
- A configurable working-hours window per tenant or branch. The window is
  fixed at 9:00 AM–6:00 PM. A tenant setting could replace the constant
  later without changing this layout.
- Changes to Month view, or to Day view's cards.
- A proportional time grid. Rejected in the previous change; still true
  with 181 visits in one hour.

## Decisions

### D1. Working-hours window inside `buildDayTimeline`

Use `WORK_START = 9` and `WORK_END = 18` (inclusive headings) as constants
in `calendar-grouping.ts`. Bucket the visits into 24 hours as today, then
keep an hour slot when it is in `[9, 18]` or has visits. "Any time"
stays last when it has visits.

The `frontier` index is recomputed against the filtered list. The last
loaded visit's slot always survives the filter, because it has a visit.
In-window hours after the frontier still render below the loading row.
Out-of-window hours after the frontier don't exist yet, so they appear as
their visits load. That is the spec's "Late visit appears once loaded".

*Alternative:* collapse the out-of-hours ranges into one "Before 9:00 AM
(3)" / "After 6:00 PM" row. Rejected: the user asked to list those times
when visits exist, and a single row hides which hour they're in.

### D2. Remove open-at-first-busy-hour

With at most 10 empty headings, about 240px, the working day is already
at the top. An early visit (before 9 AM) is the first slot, so opening at
the top shows it.

- Delete `PagedDayList`'s scroll layout effect, its `resetKey` prop, and
  `IN_VIEW_MARGIN`.
- Delete `data-scroll-root` and `useDayPages`'s `eventsKey`, which only
  existed for that effect.
- Keep the scroll position across load-more and refresh. Those never
  depended on the effect.

### D3. Columns: 5 from `xl` (1280px), 7 from `2xl` (1536px)

The column width classes become
`w-full sm:w-1/2 md:w-1/3 xl:w-1/5 2xl:w-[calc(100%/7)]`. This uses
Tailwind's default `2xl` = 96rem = 1536px; check that the theme doesn't
override it.

**Open at today:**
- A layout effect in `WeekBoard`, keyed on the week's first date, scrolls
  the board's `scrollLeft` to today's column `offsetLeft` when today is in
  the week.
- The browser clamps `scrollLeft` at the end, which gives the spec's "unless
  the week's end makes that impossible", and snap aligns it.
- A refresh doesn't change the key, so the board doesn't jump.
- On phones (one column) this also opens at today, which is a small
  improvement over the current Monday.

### D4. Two-line `block` card

- **Line 1:** the visitor name, `text-[13px] font-semibold truncate`.
- **Line 2:** a status dot, then `formatScheduledTime(time)` (or "Any
  time"), then ` · host` for branch scope. `text-xs`, truncated as one
  line.
- Drop the visible status word. The `title` and `aria-label` summary
  already start with the time and name and include `status.label`, so the
  status stays available as text.
- Padding `px-2.5 py-2`, `rounded-lg`, list `gap-1.5`.
- Text stays `text-text` on the fill, so the 4.5:1 contrast rule from
  `add-calendar-colours-and-theme-modes` is unchanged.

### D5. Lighter column chrome

**Header:** one row. The weekday (uppercase, muted) and the date number
sit together on the left. Today's date is in an accent circle. The count
pill is on the right ("181"), with its full "181 visits" in the
`aria-label`, which already exists. The header shrinks from about 76px to
about 44px.

**Hour headings in `block` variant:**
- Transparent background with a `backdrop-blur` strip only while stuck. In
  practice, use `bg-surface` with no border plus a hairline `border-t` on
  the section, not a full filled bar.
- `text-[11px] font-medium text-text-muted`. A busy hour is `text-text`.
- Day view keeps its current heading style.

**Body:**
- Padding `px-2 pb-2`, and a `gap-3` between hour sections.
- Column dividers stay as `border-r`.

**Scrollbars:**
- Add a `scrollbar-autohide` utility next to `scrollbar-thin` in
  `theme.css`. It is a thin, transparent thumb that gets its colour on
  `:hover` / `:focus-within`, using `scrollbar-color` and the webkit
  pseudo-elements, the same way `scrollbar-thin` is built.
- On touch devices the scrollbar is overlay already.

*Alternative:* hide scrollbars completely. Rejected: on desktop without a
trackpad the scrollbar is the only sign that a column scrolls.

## Risks / Trade-offs

- **[Status not visible as text in Week view]** → It stays in the colour
  fill, the dot, the legend chips, the tooltip and the accessible name.
  Day view keeps the label. Your choice, recorded in the spec.
- **[Laptop users no longer see the whole week at once]** → The board
  opens at today, and the rest is one sideways scroll or swipe away. The
  week's day totals are still in the period title area via Month view.
  This is your choice.
- **[Existing e2e tests assume 7 columns at 1440px and the first-busy-hour
  scroll]** → Update `test_week_columns_per_screen` (1440 → 5, add 1920
  → 7), replace `test_column_opens_at_its_first_busy_hour` with an
  opens-at-top test, and change `HOUR_LABELS` expectations.
- **[Today-scroll and `useBoardHeight` both run layout effects on the
  board]** → They touch different axes. No conflict.

## Migration Plan

Web-only. Archive `fix-page-bottom-gap-and-full-day-calendar` first,
since this change's delta is written against its synced spec. Roll back by
reverting.
