## 1. Shell bottom gap (app-shell "Page content keeps a bottom gap")

- [x] 1.1 Add a bottom-gap utility in `src/styles/theme.css` next to `p-page-content` that sizes the trailing spacer so the visible gap is 16/24/32px after `gap-page-section` (design D1)
- [x] 1.2 In `AppShell.tsx`, drop `<main>`'s bottom padding (keep top/sides); audit every `mainClassName` override (`grep -rn mainClassName src`) and apply the same change there
- [x] 1.3 In `RouteTransition.tsx`, add the non-shrinking trailing spacer to the wrapper and update its comment to explain why the gap lives inside the scrolled content
- [x] 1.4 In `PageContentLayout.tsx`, change `lg:h-full lg:min-h-0` to `lg:flex-1 lg:min-h-0` and update the comment that references RouteTransition's height
- [ ] 1.5 Check in the browser: a long page (e.g. admin form builder) scrolled to the end shows the gap at 390/820/1440px, and a `PageContentLayout` page does not scroll `<main>` at 1280px

## 2. Calendar fills the height without a hard-coded gap (design D2)

- [x] 2.1 Make the calendar page root and its view wrapper `flex-1 min-h-0` columns so the week board is the flexing last child from `lg` up
- [x] 2.2 Replace `WeekBoard`'s measured height with flex sizing plus a 420px floor; if short landscape phones need it, keep `useBoardHeight` but read the spacer height from computed style instead of `BOTTOM_GAP`
- [x] 2.3 Confirm in the browser at 1920×1080: the week board ends 32px above the bottom, `<main>` does not scroll, and the "Calendar" heading is fully visible

## 3. Full-day timeline (staff-calendar "Month, week and day views")

- [x] 3.1 In `calendar-grouping.ts`, add `buildDayTimeline(events, complete)` that returns 24 hour slots (0–23) with their loaded visits, then an "Any time" slot when it has visits, and the frontier slot index while incomplete (design D3); remove `groupBySlot` once it is unused
- [x] 3.2 In `PagedDayList.tsx`, render every slot as a section with its sticky hour heading, with a compact, muted heading for hours with no visits (D4)
- [x] 3.3 Place the sentinel and the loading / retry / "Showing X of Y" row right after the last loaded visit in the frontier slot while incomplete; put the "All N visits" footer after the last slot once complete
- [x] 3.4 Show "No visits" above the 24 headings for an empty day, in both Week columns and Day view (update `DayAgenda`'s empty branch to match)
- [x] 3.5 Add a `resetKey` prop and a once-per-key layout effect that scrolls the first slot with visits to the top of the scroll root (column body in Week, `<main>` in Day), skipping it if the user has already scrolled (D5); pass the key from `WeekBoard`'s `DayColumn` and `DayAgenda`
- [x] 3.6 Verify that loading more and an automatic refresh leave the scroll position unchanged

## 4. Tests and checks

- [x] 4.1 `e2e/test_staff_calendar.py`: 24 hour headings from 12:00 AM to 11:00 PM in Week and Day; 12:30 AM and 11:15 PM visits land under the first and last hours; "Any time" follows 11:00 PM; empty day shows "No visits" plus the headings
- [x] 4.2 `e2e/test_staff_calendar.py`: the column opens at its first busy hour; with a partially loaded busy day the progress row sits before the later hour headings, and scrolling loads more without moving earlier content
- [ ] 4.3 `e2e/test_responsive_matrix.py`: for every route, width and theme, scroll `main` to the end and assert the gap below the last element is at least the page padding for that width; assert `main` does not scroll on the week calendar from `lg` up
- [ ] 4.4 Run `npm run lint`, `npm run build` and `npm run e2e` (never alongside API pytest), and fix anything that fails
