## 1. Working-hours timeline (design D1, D2)

- [x] 1.1 In `calendar-grouping.ts`, add `WORK_START`/`WORK_END` (9, 18) and make `buildDayTimeline` keep an hour slot only when it is within 9:00 AM–6:00 PM or has loaded visits; recompute `frontier` against the kept slots
- [x] 1.2 Remove `PagedDayList`'s open-at-first-busy-hour layout effect, the `resetKey` prop and `IN_VIEW_MARGIN`; remove `data-scroll-root` from `WeekBoard` and `eventsKey` from `use-day-pages.ts`, plus their call sites in `WeekBoard`/`DayAgenda`
- [ ] 1.3 Check in the browser: a day with visits at 12:30 AM, 11 AM and 11:15 PM shows 12:00 AM, 9:00 AM–6:00 PM and 11:00 PM headings only; an empty day shows "No visits" and 9:00 AM–6:00 PM

## 2. Two-line week cards (design D4)

- [x] 2.1 Rewrite `CalendarEventChip`'s `block` variant: name line, then dot · time · host (branch scope) on one truncated line; no visible status word; keep `title`/`aria-label` summary unchanged
- [x] 2.2 Update padding/radius (`px-2.5 py-2 rounded-lg`) and the `block` list gap (`gap-1.5`) in `PagedDayList`

## 3. Roomier week board (design D3, D5)

- [x] 3.1 Change `DayColumn` widths to `w-full sm:w-1/2 md:w-1/3 xl:w-1/5 2xl:w-[calc(100%/7)]` (confirm `2xl` is 1536px in the theme)
- [x] 3.2 Add a layout effect in `WeekBoard`, keyed on the week's first date, that scrolls the board sideways to today's column when today is in the week
- [x] 3.3 Make the column header one row: weekday + date (today in an accent circle) on the left, count pill on the right; keep the existing `aria-label`/`aria-current`
- [x] 3.4 Restyle `block`-variant hour headings as a muted label on a hairline rule (busy hours in `text-text`); add `gap-3` between sections and `px-2 pb-2` body padding; leave Day view's headings unchanged
- [x] 3.5 Add a `scrollbar-autohide` utility in `src/styles/theme.css` and apply it to the column bodies
- [x] 3.6 Check in the browser at 1280, 1440 and 1920px in both themes: 5/5/7 columns, opens at today, two-line cards, no page scroll, thin scrollbars on hover

## 4. Tests and checks

- [x] 4.1 Update `e2e/test_staff_calendar.py`: `HOUR_LABELS` → working-hours expectations; `test_day_view_shows_every_hour` / `test_week_column_shows_every_hour` assert 12:00 AM, 9:00 AM–6:00 PM, 11:00 PM; empty day asserts 9:00 AM–6:00 PM
- [x] 4.2 Replace `test_column_opens_at_its_first_busy_hour` with an opens-at-top test; update `test_unloaded_hours_sit_below_the_progress_row` to use "6:00 PM"
- [x] 4.3 Update `test_week_columns_per_screen` to 390→1, 820→3, 1440→5, 1920→7, and add a check that the current week opens with today's column visible
- [x] 4.4 Add a Week-view test that a card has no visible status word but its accessible name includes it
- [ ] 4.5 Run `npm run lint`, `npm run build` and `npm run e2e -- test_staff_calendar.py`, plus the device-width matrix at 390/820/1280/1920px, and fix anything that fails
