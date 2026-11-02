## Context

See proposal.md (Why) for the three faults found in the browser. This
section covers the layout that produces them.

- **Shell.** `<main>` is the only page scroller (`AppShell`).
  `RouteTransition`'s wrapper is `h-full flex-col`, and its last child
  is the `h-page-end-gap` spacer that makes the bottom gap
  (fix-page-bottom-gap-and-full-day-calendar D1).
- **`PageContentLayout`.**
  - From `lg` up, it splits a page into a fixed `header`, a body
    (`lg:flex-1 lg:min-h-0 lg:overflow-y-auto`) and an optional `footer`
    slot.
  - Every paged admin list puts `<Pagination>` inside the body, under
    the table, inside `AsyncRegion`. That is why the pagination scrolls
    away.
  - The `footer` slot already exists. Its doc comment says it is "pinned
    below the scrolling region". Only wizard action bars use it today.
- **Week view.**
  - From `lg` up, the calendar page root and its view wrapper are
    `lg:flex-1 lg:min-h-0`. The board is `lg:flex-1 lg:min-h-[420px]`.
  - When less than 420px is free, the floor makes the board overflow a
    root that has already shrunk. The board then runs past the window,
    and the end-gap spacer stays behind the shrunk root instead of
    following the board.
  - Below `lg`, `useBoardHeight` measures the free height and sets an
    explicit pixel height. That works, because content with an explicit
    height overflows in order and the spacer follows it.
- **Day view.**
  - `DayAgenda` is a plain card that grows with its content. The page
    scrolls, and `PagedDayList`'s IntersectionObserver uses `<main>` as
    its root.
  - `PagedDayList` renders the sentinel and the status row (`DayListFooter`)
    at the loading frontier, and `All N visits` after the last slot. The
    status therefore always sits inside the scrolled content.

## Goals / Non-Goals

**Goals:**
- One way to pin pagination on every paged list: the existing `footer`
  slot, with no new layout component.
- One way to size calendar panels that fill the height (Week board, Day
  card). It must keep a floor and the shell's bottom gap.
- The scroll-position, refresh and lazy-loading behaviour of Week
  columns stays as it is.

**Non-Goals:**
- Sticky table header rows inside the scrolling list body. They are worth
  doing, but each table has its own wrapper, so that is a separate change.
- Sticky pagination on phones. Below `lg` the page scrolls as one, and
  the footer follows the rows, as it does today.
- Month view, invitation boards (their columns already pin their own
  load-more), and form pages.
- Page-size selectors, or any change to what pagination shows.

## Decisions

### D1. Pagination moves into `PageContentLayout`'s `footer` slot

Each paged list passes `<Pagination>` as `footer`, wrapped in
`flex-none`, only while the list is ready and not empty:

```tsx
footer={phase === 'ready' && rows.length > 0 ? <div className="flex-none"><Pagination …/></div> : undefined}
```

- From `lg` up, the layout root is a flex column. The header is fixed,
  the body takes the rest and scrolls, and the footer takes its own
  height. The footer can't scroll away.
- Below `lg`, nothing flexes. The footer is a plain block after the body,
  so it follows the last row (responsive-layout "Paged List Pagination
  Stays Visible Below the Data").
- **Short lists.** Today the body is `lg:flex-1`, so with three rows it
  would stretch and push the footer to the window bottom. Add an opt-in
  `fitBody` prop to `PageContentLayout`.
  - When set, the body is `lg:flex-initial lg:min-h-0 lg:overflow-y-auto`
    (flex `0 1 auto`). It is as tall as its rows, but shrinks and scrolls
    once they exceed the free height, so the footer sits right under
    short lists.
  - Paged lists pass `fitBody={rows.length > 0}`. The empty and error
    states keep `flex-1`, so their centred panels still fill the page.
  - The default stays `flex-1`, so the boards and wizards that already
    use `PageContentLayout` (and its `footer`) are unchanged.
- The gate is `phase === 'ready'` and not "refreshing". On a re-fetch,
  `AsyncRegion` keeps the old rows on screen (async-ui-states "Re-fetching
  keeps existing content visible"), so the footer stays too, as it does
  today.
- `Pagination` keeps its `border-t pt-3`. The body/footer gap comes from
  the layout's existing `gap-4 md:gap-6`.

*Alternative considered:* making `Pagination` itself `sticky bottom-0`
inside the body. That works from `lg` up, but it covers the last row,
needs a background and shadow, and behaves differently with the
table's own horizontal scroller. The footer slot already exists for this.

### D2. The workflows list uses the shared `Pagination`

`WorkflowListTable` renders its own `Showing A-B of N workflows` footer
inside the table component, so it can't be moved without lifting it out.

- Lift it into `admin-workflows.tsx`'s `footer`, using the shared
  control.
- Add an optional `itemLabel` prop (default `'results'`) to `Pagination`,
  so the text stays `… of N workflows`.
- The buttons change from "Previous"/"Next" text buttons to the shared
  icon buttons. They keep the same `aria-label`s, so the workflows page
  matches every other list.

### D3. Fill-height calendar panels are measured, not flexed

The current desktop approach is flex sizing (`flex-1` + `min-h-0` +
floor). It can't do both jobs at once: a floor on a flex item inside a
`min-h-0` parent overflows the parent, and the end-gap spacer ends up in
the wrong place. Removing `min-h-0` lets the parent's intrinsic height
pull in the full column content.

Instead, generalise `useBoardHeight` into `useFillHeight(ref, { floor,
enabled })`, which sets an explicit pixel height:
- **Height:** `max(floor, main.clientHeight − top-of-element-in-main −
  bottom gap)`. The bottom gap is read from computed style, as today.
- **Re-measure when:** the window is resized or rotated, and when the
  block above the panel (page header + toolbar) changes size, through a
  `ResizeObserver` on that block. That block wraps when the branch
  selector appears or the sidebar collapses. Don't observe `<main>`'s
  content: the panel's own height changes it, which would loop.
- **Week board:** enabled at every width. The floor is 240px from `lg`
  up and stays 420px below `lg`.
- **Day card:** enabled from `lg` up, with a 240px floor. Below `lg` it
  stays content-sized (staff-calendar "Day view scrolls its timeline
  inside its own panel").
- The calendar page drops `fillClass` (`lg:min-h-0 lg:flex-1`) from its
  root and view wrapper. With explicit heights, everything is
  content-sized. A window that is too short just makes `<main>` scroll,
  and the spacer follows the panel, which keeps the bottom gap.

Why 240px: the column header (about 45px), the column footer (about
32px) and roughly four hour rows still fit. That is enough to read
and scroll. 1280×720 leaves about 360px, so it fits with room to spare.

*Alternative considered:* keep flex sizing and only lower the floor to 0.
That fixes 1280×720, but on very short windows the columns collapse to
a few pixels. It also drops the guarantee that the panel's bottom edge
can be reached.

### D4. The paging status moves out of the scrolled list

`PagedDayList` keeps:
- the timeline;
- the sentinel at the frontier;
- a slim frontier row (`data-load-frontier`) that shows "Loading more…"
  while a page loads and is otherwise an empty 1px marker.

The `Showing X of Y` / `All N visits` / Retry status moves to an exported
`DayListStatus` component. Each parent renders it in a `shrink-0 border-t`
footer below its scroll body:
- `WeekBoard`'s `DayColumn`: header, body, footer.
- `DayAgenda`: header, body, footer.
- The parent hides it when `total === 0`.

This keeps the pending spec's "loading row after the last loaded visit"
and "unloaded hours sit below the progress row" behaviour. The frontier
row is still the in-list marker, and the count becomes visible without
scrolling.

### D5. Day card layout

`DayAgenda` becomes a three-row flex column inside the measured card:
- **Header (`shrink-0`):** the long date on the left and a count pill on
  the right, matching the Week column header's pill style. The toolbar
  already shows the date, but it also shows the range controls, so the
  card header labels the panel and stays visible next to the visits.
- **Body:** `min-h-0 flex-1 overflow-y-auto overscroll-contain
  scrollbar-autohide`. A `bodyRef` is passed as `scrollRootRef`, so the
  IntersectionObserver and the sticky hour headings use the card, not
  `<main>`.
- **Footer (`shrink-0`):** D4's status.

Below `lg` the card has no explicit height, so the body doesn't overflow.
The page scrolls, the footer follows the last visit, and the
IntersectionObserver must use `<main>`. So pass `scrollRootRef` only when
the card is height-bound (`useIsDesktop()`). The observer effect already
depends on `scrollRootRef`, so a breakpoint change re-attaches it.

## Risks / Trade-offs

- **[Risk]** Measuring adds a frame where the panel is 240px before the
  first measure.
  → The measure runs in `useLayoutEffect`, before paint, as
  `useBoardHeight` does today.
- **[Risk]** The `ResizeObserver` on the header and toolbar block can
  miss a size change that comes from somewhere else (for example, an
  error banner inserted above the panel).
  → Error states replace the panel entirely in `calendar-page.tsx`, so
  there is no other sibling above it. A comment in the hook should say
  this.
- **[Trade-off]** Moving pagination out of `AsyncRegion` means each page
  repeats the `ready && rows.length > 0` gate (10 pages).
  → It's one expression per page. A wrapper component would hide the
  `footer` slot the layout already documents.
- **[Risk]** e2e helpers scroll `<main>` to page Day view
  (`_scroll_day_until`, `test_day_view_pages_by_twenty`), and
  `test_unloaded_hours_sit_below_the_progress_row` locates the progress
  row by its `Showing` text. Both break.
  → Tasks update them to scroll the Day card body at desktop width, and
  to anchor on `[data-load-frontier]`.

## Migration Plan

Front-end only, with no API or data changes. Deploy with the web build.
To roll back, revert the commit.

## Open Questions

- Whether the Day card header should also show per-status counts (for
  example "3 inside · 2 expected"). This can be added later inside the
  header row without changing this layout.
