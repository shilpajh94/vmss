## 1. Bottom gap below 1024px (design D1)

- [x] 1.1 Probe: at 390px on `/admin/dashboard`, give the end-gap spacer 1px in devtools/`page.evaluate` and confirm `endGap` goes from ~0 to ~16. If it doesn't, stop and revise design D1
- [x] 1.2 In `src/styles/theme.css`, change `h-page-end-gap` to the page padding (16/24/32px) with a negative top margin equal to `gap-page-section` (16/24/24px), and update the comments in `theme.css` and `RouteTransition.tsx`
- [x] 1.3 Run `npm run e2e -- test_responsive_matrix.py` and confirm every width passes in both themes

## 2. Status filter resets column scroll (design D2, staff-calendar "Status filter, truncation and empty states")

- [x] 2.1 In `WeekBoard.tsx` `DayColumn`, reset the column body's `scrollTop` to 0 in a layout effect keyed on day/branch/statuses (not on a refresh)
- [x] 2.2 In `DayAgenda.tsx`, do the same for the Day list's scroller on a new day/branch/statuses
- [x] 2.3 Confirm `test_status_filter_resets_columns` and `test_refresh_keeps_loaded_visits_and_scroll_position` pass

## 3. Date- and data-independent tests (design D3–D5)

- [x] 3.1 Add `_show_column(page, day)` to `e2e/test_staff_calendar.py` and use it in `test_week_column_status_is_in_view_without_scrolling` and in any other test that asserts a specific column is in the viewport
- [x] 3.2 In `test_week_column_shows_working_hours_and_busy_out_of_hours`, load the 2 Dec column to the end before asserting the early and late visits
- [x] 3.3 In `e2e/test_invitation_lifecycle.py`, wait for the approver's dialog to close before reading the invitation status
- [x] 3.4 Run `npm run e2e -- test_staff_calendar.py test_invitation_lifecycle.py` and confirm they pass

## 4. Full check

- [x] 4.1 Run `npm run lint` and `npm run build`
- [x] 4.2 Run the full `npm run e2e` (never alongside API pytest) and confirm 0 failures; fix anything new
- [x] 4.3 Tick `calendar-page-scroll-and-taller-panels` task 3.7
