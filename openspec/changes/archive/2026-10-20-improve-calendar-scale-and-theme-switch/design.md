## Context

See proposal.md for motivation. The API half (`perDayLimit`, the paged
`GET /invitations/calendar/day`, total ordering) is designed in VMSS_API
`openspec/changes/improve-calendar-scale-and-theme-switch/design.md`.

Current web state:

- **Calendar.**
  - `useCalendarFeed` fetches the whole range through
    `useLiveResource`/`useLiveDashboard` (polling every 10s, refetch on
    invitation activity, top-bar refresh).
  - `WeekView` is a CSS grid of 7 day columns × (Any time + hour) rows,
    with every event of every day rendered.
  - `DayAgenda` renders every event of the day.
  - `MonthGrid` shows 3 chips plus "+N more" from `days[].total`.
- **Theme.**
  - `ThemeModeProvider` stores the mode; `useApplyTheme` sets
    `data-theme` in a layout effect.
  - `useChartTheme` re-reads tokens in a passive effect, so the charts
    recolour one render later.
  - About 33 `transition-colors` and the shared `PRESS_FEEDBACK_CLASS`
    (`transition-[background-color,color,border-color,…] duration-fast`)
    fade colour changes at 100–180ms.
  - `ThemeModeMenu` closes with the `motion-popover` exit animation.
- **Responsive.** A sweep of 31 routes × 9 widths found overflow only on:
  - `/admin/organisation-configs` at ≤414px: a settings row's
    title/description/toggle doesn't wrap;
  - `/admin/audit-trail` at ≤414px: `AuditFilterBar` is one non-wrapping
    flex row (select + `ml-auto` CSV/PDF buttons), and the results list
    rows have fixed-ratio columns.

  `main` clips horizontal overflow, so that content is unreachable.

## Goals / Non-Goals

**Goals:**
- A week board whose height is bounded by the viewport, with independent
  per-day scroll and server-paged lazy loading.
- A one-frame theme switch with no staggered fades and no late chart
  recolour.
- No overflow on any staff/admin route at the supported widths, enforced by
  a test.

**Non-Goals:**
- List virtualisation. Paging caps what's in the DOM at the visits the user
  actually scrolled to. A day of 1,000+ visits scrolled to the end is
  acceptable at about 1,000 small chips.
- Redesigning the month grid.
- Theming the public pages.

## Decisions

### W1. Week = `WeekBoard` of seven `DayColumn`s

`WeekBoard` is a horizontally scrolling flex row with `scroll-snap-type: x
mandatory`. Each `DayColumn` is
`flex-none snap-start w-full sm:w-1/2 md:w-1/3 xl:w-[calc(100%/7)]`
(1/2/3/7 per screen). The board's height is
`h-[calc(100dvh-<toolbar+header offset>)]`, with a minimum of 420px. It is
computed from the board's own top on mount and resize
(`getBoundingClientRect().top`), so it fills the remaining viewport on
every device without hard-coding the toolbar height.

Each `DayColumn` has:
- a sticky header (weekday, date, exact `days[].total`, today highlight;
  click opens Day view);
- an `overflow-y-auto overscroll-contain` body;
- grouping headers for "Any time" and each hour, `sticky top-0` inside the
  body;
- the existing `CalendarEventChip` block variant;
- a footer: "Showing X of Y", a loading row, a retry, or nothing when
  complete.

*Alternative:* keep the hour grid with per-cell scroll (rejected by the
user). It also yields dozens of tiny scroll areas.

### W2. First page from the feed, more from the day endpoint

`useCalendarFeed` adds `perDayLimit`:

| View | `perDayLimit` |
|---|---|
| Month | 3 |
| Week | 10 |
| Day | none: Day view doesn't use the feed for its list |

Week columns are seeded from the feed's events for that date, which are
the first 10. When the column's sentinel (an `IntersectionObserver` on the
last chip, `rootMargin: 200px` inside the column) becomes visible and
`loaded < total`, it fetches `GET /invitations/calendar/day?date=…&page=
⌊loaded/10⌋+1&pageSize=10` with the same branch and statuses. Results are
appended and de-duplicated by `id`.

Day view seeds nothing from the feed. It pages the day endpoint with
`pageSize=20` (page 1 at once, then on scroll), using the same hook.

### W3. `useDayPages(date, query, seed?)`: per-column paging state

State is `{ events, total, nextPage, status: idle|loading|error|done }`,
keyed by `date|branch|statuses`. When the key changes, it resets to the
seed. Concurrent loads are guarded per column.

On refresh (the live tick, a manual refresh, or invitation activity),
each column re-requests its already-loaded window as one call:
`page=1&pageSize=min(loaded, 100)`. Above 100, it re-requests in
100-sized pages up to `loaded`. The list is replaced in place and keeps
`scrollTop`, because the DOM node and its children are keyed by
invitation id, so React only patches changed chips.

The feed's own refresh updates the totals and the seed.
`useLiveDashboard` already throttles polling to visible tabs.

### W4. Theme switch in one frame

1. **Apply synchronously.** `ThemeModeProvider` keeps a ref to the current
   page scope (`'themed' | 'light'`), registered by `useApplyTheme`.
   `setMode` and the `matchMedia` change handler compute the new resolved
   theme and write `data-theme` on `<html>` immediately, before the React
   state update. The layout effect remains as the reconciler for route
   changes.
2. **Suspend transitions.** Around the write, set
   `<html data-theme-switching>`. `index.css` has
   `[data-theme-switching] *, [data-theme-switching] *::before,
   [data-theme-switching] *::after { transition: none !important;
   animation: none !important }`. Remove it after two
   `requestAnimationFrame`s, once styles have recalculated with the new
   tokens.
3. **Optional cross-fade.** If `document.startViewTransition` exists and
   `prefers-reduced-motion` is not `reduce`, wrap the write in it. Add
   `::view-transition-old(root), ::view-transition-new(root) {
   animation-duration: 150ms }`. Otherwise do a plain instant write.
4. **Charts read in render again.** `useChartTheme` goes back to
   `useMemo(read, [resolved])`. Because of step 1, `<html>` already
   carries the new theme when the charts render, so they recolour in the
   same frame. That reverts the passive-effect workaround.
5. **The menu closes without an exit animation on selection.** It
   unmounts immediately (`usePresence` is bypassed for the select path)
   and focus returns to the button.

*Alternative:* a CSS-only `transition: background-color 200ms` on
everything. Rejected because it is exactly the staggered "wave" users
see now.

### W5. Responsive fixes and the guard

- **Organisation configs.** Settings rows become
  `flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`.
  The text block gets `min-w-0`, and the toggle gets `shrink-0
  self-start sm:self-auto`.
- **Audit filter bar.** `flex flex-wrap`. The select becomes `w-full
  sm:w-auto`. The CSV/PDF group becomes `w-full sm:w-auto sm:ml-auto`,
  with buttons `flex-1 sm:flex-none`.
- **Audit result rows.** Below `md`, label/value pairs stack (the
  `responsive-table` card pattern), or the table scrolls inside its own
  container.
- **Guard.** `e2e/test_responsive_matrix.py` runs every staff and admin
  route × 10 widths × 2 themes. It asserts that document and `main`
  overflow are 0, that the header height is ≤72px (one row), and that no
  unclipped element extends past the viewport. Runtime is about 600 page
  loads, so it's marked `slow` and run in the full e2e pass.

## Risks / Trade-offs

- **Nested scroll on touch devices** can trap the page scroll. →
  `overscroll-contain` on columns. The board's height leaves the toolbar
  reachable, and the page itself has little else to scroll in Week view.
- **Board height calculation** with on-screen keyboards or `dvh` support.
  → Use `100dvh` with a `100vh` fallback, and recompute on `resize` and
  `orientationchange`.
- **Synchronous apply diverges from React state** if a render throws. →
  The layout effect re-asserts the attribute from state on every commit,
  so any divergence self-heals on the next render.
- **View Transitions:** Chrome and Edge support them, and Safari 18+ does;
  Firefox falls back to the instant switch, which is acceptable.
- **Matrix runtime.** It's marked slow. The PR checklist runs it for any
  layout change; otherwise it runs nightly or with the full suite.

## Migration Plan

Deploy the API change first. This change is client-only, and rollback is a
revert. With the old API, `perDayLimit` is ignored (no limit), so the week
board still works but columns start with every visit. The day endpoint
404s, so "load more" shows a retry. Ship them together.
