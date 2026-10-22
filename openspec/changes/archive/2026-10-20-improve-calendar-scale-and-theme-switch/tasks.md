Depends on VMSS_API `improve-calendar-scale-and-theme-switch` (deploy first).
Never run prettier in VMMS_WEB. Never run e2e alongside the API's pytest.

## 1. Data layer

- [x] 1.1 `api-endpoints.ts`: add `GET_CALENDAR_DAY: '/invitations/calendar/day'`.
  `calendar-feed-schema.ts`: add a paged day response schema, reusing
  `CalendarEventSchema` plus the standard `pagination`.
- [x] 1.2 The calendar repository interface and implementation:
  - `getFeed` gains `perDayLimit`;
  - new `getDayPage({ date, page, pageSize, branchId?, statuses? })`
    returning `{ events, total, scope }` (scope from `X-Calendar-Scope`,
    falling back to the feed's).
  - Wire a `GetCalendarDayPageUseCase` in `composition-root.ts`.

## 2. Paging hook

- [x] 2.1 `pages/calendar/hooks/use-day-pages.ts` (design.md W3):
  - seeded or empty start, keyed reset;
  - `loadMore()` with a per-column in-flight guard and id de-dup;
  - `status` of idle/loading/error/done;
  - `refresh()` re-requests the loaded window in 100-sized calls.
- [x] 2.2 `use-calendar-feed.ts`: send `perDayLimit` (month 3, week 10) and
  expose a `refreshTick` so the columns refresh alongside the feed.

## 3. Week board

- [x] 3.1 `WeekBoard.tsx`:
  - a snap-scrolling row of 7 columns (1/2/3/7 per screen at
    `<sm`/`sm`/`md`/`xl`);
  - viewport-filling height from its own top, recomputed on resize and
    orientation change (`100dvh` with a `vh` fallback, min 420px) (W1).
- [x] 3.2 `DayColumn.tsx`:
  - a sticky day header with the exact total and today highlight; a click
    opens Day view;
  - an `overflow-y-auto overscroll-contain` body with sticky
    "Any time"/hour headings;
  - block chips;
  - an `IntersectionObserver` sentinel (`rootMargin` 200px) that calls
    `loadMore`;
  - a footer with "Showing X of Y", a loading row, a retry, or nothing;
  - "No visits" when empty.
- [x] 3.3 Replace `WeekView` with `WeekBoard` in `calendar-page.tsx`.
  Delete `WeekView.tsx` and any grouping helpers left unused.

## 4. Day and month

- [x] 4.1 `DayAgenda`: page the day endpoint (`pageSize` 20) via
  `useDayPages`, with sticky hour groups, a sentinel, a footer and a
  retry.
- [x] 4.2 `MonthGrid` uses the feed with `perDayLimit=3`. Remove the
  truncation banner and its copy from `calendar-page.tsx`.

## 5. Theme switch

- [x] 5.1 `theme-mode-context.tsx` (design.md W4):
  - a scope ref registered by `useApplyTheme`;
  - `applyThemeNow(resolved)` with a `data-theme-switching` guard
    (removed after 2 rAFs) and an optional `startViewTransition` (skipped
    under reduced motion);
  - called from `setMode` and the `matchMedia` handler before the state
    update;
  - the layout effect stays as the reconciler.
- [x] 5.2 `index.css`: add the `[data-theme-switching]`
  transition/animation suppression rule and a 150ms
  `::view-transition-old/new(root)` duration.
- [x] 5.3 `chart-theme.ts`: back to `useMemo(read, [resolved])`, now
  correct because the attribute is applied first.
- [x] 5.4 `ThemeModeMenu`: selecting an option unmounts the menu
  immediately (no exit animation) and returns focus. Escape and an outside
  click keep the animated close.

## 6. Responsive fixes

- [x] 6.1 `admin-organisation-configs.tsx`: settings rows stack below `sm`
  (W5).
- [x] 6.2 `AuditFilterBar.tsx`: wrap, a full-width select and button group
  on phones. Make the audit results rows fit below `md` (stacked
  label/value, or contained scroll).
- [x] 6.3 Fix anything else the matrix (7.3) reports.

## 7. Verification

- [x] 7.1 Run `tsc -b`, `npm run lint` (all checks) and `npm run build`.
- [x] 7.2 `e2e/test_staff_calendar.py`. Using the QA tenant's busy Monday
  (100+ visits):
  - the page height doesn't grow with visits;
  - Monday shows 10 and "Showing 10 of N";
  - scrolling the column appends 10 and updates the footer;
  - scrolling to the end shows N unique visits and stops loading;
  - Tuesday is unaffected;
  - a refresh keeps 40 loaded at the same `scrollTop`;
  - Day view pages by 20;
  - a status-filter change resets the columns;
  - one column at 390px with snap, three at 820px;
  - no truncation banner.
- [x] 7.3 `e2e/test_responsive_matrix.py` (marked slow): every staff and
  admin route (all three calendar views included) × 10 widths × light and
  dark. Assert document overflow 0, `main` overflow 0, a header of one row
  (≤72px), and no unclipped element past the viewport.
- [x] 7.4 `e2e/test_theme_mode.py`:
  - after a switch, the first frame's chart axis colour and the card
    background are both dark (sampled in the same rAF);
  - a `PRESS_FEEDBACK` button's background reaches its dark value
    immediately (no transition);
  - `data-theme-switching` is gone afterwards, and hover transitions
    work;
  - reduced motion skips the view transition;
  - the menu is unmounted by the first repainted frame.
- [x] 7.5 Re-run the dashboards, auth, calendar and theme suites, and
  review screenshots of the week board (light/dark × 390/820/1440).

## Implementation notes

- **Day view starts from the feed.** Day view requests the feed with
  `perDayLimit` 20 and seeds `useDayPages` from it, so the first 20 visits
  come with the feed instead of a separate day-page call. Later pages come
  from the day endpoint.
- **One list component.** `DayColumn` lives inside `WeekBoard.tsx`, and the
  week columns and Day view share `PagedDayList.tsx` (sticky headings,
  sentinel, footer, retry) instead of separate copies.
- **No `refreshTick`.** A feed refresh hands each column a new seed for the
  same key. A column that has loaded no more than the seed adopts it.
  Otherwise it re-requests its loaded window in 100-sized calls.
- **"Any time" comes last.** The standard order puts visits with no time
  last (nulls last), so the "Any time" group is last too. It isn't
  re-sorted to the top, because that would break paging order.
- **Scope comes from the feed.** `makeRequest` doesn't expose response
  headers, so the web reads the applied scope from the feed rather than
  from `X-Calendar-Scope`.
- **Board height.** Measured from the board's top inside the `main`
  scroller, with min 420px and a 24px bottom gap, rather than `100dvh`
  arithmetic (the header height differs by device).
- **Responsive root causes.**
  - Organisation configs: its cards sat side by side below `lg`. They
    now stack.
  - Audit trail: the filter row didn't wrap, and the table wrapper had no
    `min-w-0`.
  - The matrix (6.3) then found two more at 320px. Visitor-category badge
    colour buttons didn't wrap (`BadgeColorField`). The workflow approver
    select's `flex-1` wrapper had no `min-w-0`, which pushed the remove
    button out (`admin-workflow-form.tsx`).

## Verification results (2026-10-20)

Run against a production build (`vite preview`), because the dev server
timed out under the long matrix. Another change,
`fix-page-bottom-gap-and-full-day-calendar`, was in progress at the same
time, so the build includes its unfinished work.

- **7.1:** `tsc -b`, `npm run lint` and `npm run build` pass. The two lint
  warnings are in an untouched file.
- **7.3:** all 20 width × theme cases pass this change's checks: document
  overflow 0, `main` overflow 0, and a header of 72px or less. Some
  failures remain only on the bottom-gap check (`endGap`), which the
  other change added to the test and has not finished yet.
- **6.3:** the matrix found two more 320px overflows, both fixed.
  - `BadgeColorField`: `flex-wrap`.
  - `admin-workflow-form.tsx`: `min-w-0` on the approver select wrapper.
- **7.5:** dashboards, auth, calendar and theme suites: 77 passed and 2
  xfailed (known issues). Two calendar tests failed during the long run
  and passed on a rerun in isolation, so they are load-timing flakes:
  - `test_more_link_opens_the_day…`
  - `test_refresh_keeps_loaded_visits…`

  Week-board screenshots at 390/820/1440, light and dark: 1/3/7 columns,
  columns scroll on their own, and the page height stays fixed.
