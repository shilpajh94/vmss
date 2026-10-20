## 1. Visible-page sizing (staff-calendar "Week board and Day card are as tall as the visible page", design D1–D2)

- [x] 1.1 In `use-fill-height.ts`, compute `max(floor, main.clientHeight − main.paddingTop − bottomGap)` without the element's top. Replace the `observeRef` observer with a `ResizeObserver` on `<main>`, keep the resize/orientation listeners, drop the `observeRef`/`remeasureKey` options, and rewrite the header comment
- [x] 1.2 Use one `PANEL_FLOOR = 420` for the Week board (every width) and the Day card (`lg`+); remove `DESKTOP_BOARD_FLOOR`/`MOBILE_BOARD_FLOOR`/`DAY_CARD_FLOOR` and the `useIsDesktop` floor switch in `WeekBoard`
- [x] 1.3 In `calendar-page.tsx`, remove the `controlsRef` wrapper div (re-indent the header and toolbar back) and the `controlsRef`/`remeasureKey` props; keep `isEmptyRange` for the empty-week notice; drop the props from `WeekBoard` and `DayAgenda`

## 2. Scroll hand-over (design D3)

- [x] 2.1 Remove `overscroll-contain` from the Week column body and `lg:overscroll-contain` from the Day card body; keep the board's `overscroll-x-contain`
- [x] 2.2 Check in the browser at 1280×720 and 1920×1080: the board and card are as tall as the visible page area, the page scrolls by the title + toolbar height, the bottom gap follows the panel, a wheel past a column's end scrolls the page, and the hour headings stay sticky; at 390×844 the Week board fills the visible area and Day view scrolls with the page

## 3. Tests and checks

- [x] 3.1 `e2e/test_staff_calendar.py`: in `test_busy_day_scrolls_inside_its_column`, replace the `overflow == 0` check with "board height equals the visible page area"
- [x] 3.2 Rewrite `test_week_board_leaves_the_page_gap_without_scrolling_the_page` and `test_week_board_fits_a_laptop_window` to assert board height = visible page area (±1px) and, after scrolling `main` to the end, a 32px gap below the board
- [x] 3.3 Rewrite `test_day_view_scrolls_inside_its_card`: card height = visible page area, `main` scrolls by more than 0, loading more works from the card body, and scrolling `main` back to the top shows the `Calendar` heading and the period title
- [x] 3.4 In `test_week_column_status_is_in_view_without_scrolling`, scroll `main` to the end before asserting that the column footer is in the viewport (the column itself stays at `scrollTop` 0)
- [x] 3.5 Add a hand-over test: with `main` at the top and a column body scrolled to its end, `page.mouse.wheel` over the column moves `main.scrollTop` (allow the next-gesture behaviour from design D3 by wheeling twice)
- [x] 3.6 `e2e/test_responsive_matrix.py`: remove `view=day` and `view=week` from the "main does not scroll" check (keep the end-gap check)
- [x] 3.7 Run `npm run lint`, `npm run build` and `npm run e2e -- test_staff_calendar.py` (never alongside API pytest), and fix anything that fails
