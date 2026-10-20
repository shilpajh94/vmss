## 1. Pinned pagination on paged lists (responsive-layout "Paged List Pagination Stays Visible Below the Data")

- [x] 1.1 Add the opt-in `fitBody` prop to `PageContentLayout` (body `lg:flex-initial lg:min-h-0 lg:overflow-y-auto` when set; default unchanged) and update its doc comment (design D1)
- [x] 1.2 Add an optional `itemLabel` prop (default `'results'`) to `Pagination` (design D2)
- [x] 1.3 Move `<Pagination>` from the body into `footer` (wrapped in `flex-none`, shown only when `phase === 'ready'` and there are rows) and pass `fitBody={rows.length > 0}` on: `admin-branches`, `admin-buildings`, `admin-floors`, `admin-departments`, `admin-roles`, `admin-host-employees`, `admin-visitor-categories`, `admin-kiosks`, `admin-devices`, `admin-audit-trail`. Remove the now-empty `flex-col gap` wrappers around each table
- [x] 1.4 Lift the footer out of `WorkflowListTable` into `admin-workflows.tsx`'s `footer`, using the shared `Pagination` with `itemLabel="workflows"`; drop the unused paging props from `WorkflowListTable`
- [x] 1.5 `grep -rn "<Pagination" src` and confirm that no paged list still renders it inside the body
- [x] 1.6 Check in the browser at 1280×720, 1440×900 and 390×844: a 20-row list shows its footer without scrolling, a 3-row list has the footer directly under its rows, a phone-width page scrolls as a whole with the footer after the last row, and an empty list shows no footer

## 2. Fill-height sizing for calendar panels (design D3)

- [x] 2.1 Generalise `WeekBoard`'s `useBoardHeight` into a `useFillHeight(ref, { floor, enabled, observeRef })` hook in `pages/calendar/hooks/`: explicit height `max(floor, main.clientHeight − top − bottom gap)`, measured in a layout effect, re-measured on resize/orientation change and through a `ResizeObserver` on the header/toolbar block
- [x] 2.2 In `calendar-page.tsx`, drop `fillClass` from the root and the view wrapper; wrap the title and toolbar in one element and pass its ref down as `observeRef`
- [x] 2.3 In `WeekBoard`, use the hook at every width (floor 240px from `lg` up, 420px below) and remove `lg:flex-1 lg:min-h-[420px]`
- [x] 2.4 Check in the browser: at 1280×720 and 1366×768 the board ends at the bottom gap and `<main>` doesn't scroll; at 1920×1080 the same; at 1280×500 the board is 240px, `<main>` scrolls, and the gap follows the board

## 3. Paging status in fixed footers (staff-calendar "Each day's paging status stays visible", design D4)

- [x] 3.1 In `PagedDayList`, replace the frontier progress row with a slim `data-load-frontier` row (sentinel, plus "Loading more…" while loading) and remove the end-of-list `All N visits` footer
- [x] 3.2 Export the count/Retry part as `DayListStatus` (`Showing X of Y`, `All N visits`, Retry on error) with `role="status"`
- [x] 3.3 In `WeekBoard`'s `DayColumn`, render `DayListStatus` in a `shrink-0 border-t` footer under the column body, hidden when `total === 0`

## 4. Day view scrolling panel (staff-calendar "Day view scrolls its timeline inside its own panel", design D5)

- [x] 4.1 Restructure `DayAgenda` as a three-row card: header (long date + count pill, Week header pill style), body (`min-h-0 flex-1 overflow-y-auto overscroll-contain scrollbar-autohide`), footer (`DayListStatus`, hidden on an empty day)
- [x] 4.2 Size the card with `useFillHeight` (floor 240px, enabled from `lg` up only); below `lg` the card stays content-sized
- [x] 4.3 Pass the body ref as `scrollRootRef` only when the card is height-bound (`useIsDesktop()`), so lazy loading observes the card from `lg` up and `<main>` below it
- [x] 4.4 Check in the browser at 1440×900 and 1280×720: a busy day does not scroll the page, the toolbar and card header/footer stay put, scrolling the card loads the next 20 without a jump, and an automatic refresh keeps the card's scroll position; at 390×844 the page scrolls as before

## 5. Tests and checks

- [x] 5.1 `e2e/test_responsive_matrix.py` (or a new paged-list test): at 1280×720 and 1440×900, every paged admin list (including workflows) has its `Showing …` text and Previous/Next buttons inside the viewport without scrolling, and `<main>` doesn't scroll
- [x] 5.2 `e2e/test_staff_calendar.py`: update `_scroll_day_until` and `test_day_view_pages_by_twenty` to scroll the Day card body at desktop width; update `test_unloaded_hours_sit_below_the_progress_row` to anchor on `[data-load-frontier]`
- [x] 5.3 `e2e/test_staff_calendar.py`: add tests that Day view at 1440×900 doesn't scroll `<main>` and keeps the toolbar visible after scrolling the card, that a Week column's `Showing X of Y` is in view without scrolling the column, and that the Week board's bottom edge is inside a 1280×720 viewport with `<main>` not scrolling
- [ ] 5.4 Run `npm run lint`, `npm run build` and `npm run e2e` (never alongside API pytest), and fix anything that fails
