## Context

See proposal.md (Why). Current state, from
`fix-paging-footers-and-calendar-day-scroll`:

- **Sizing.** `useFillHeight` gives the Week board (every width) and the
  Day card (`lg`+) an explicit height:
  `max(floor, main.clientHeight − panelTop − bottomGap)`.
  - The floor is 240px from `lg` up and 420px below.
  - It re-measures on resize and through a `ResizeObserver` on the
    title/toolbar block (`controlsRef`), plus a `remeasureKey` for the
    empty-week notice.
- **Scrolling.** The week column bodies have `overscroll-contain`, and
  so does the Day card body (`lg:overscroll-contain`). That stops scroll
  chaining. While the panel fits under the toolbar that's harmless,
  because the page can't scroll anyway. Once the page scrolls, it would
  trap the wheel inside the panel.
- **Week board.** It has `overscroll-x-contain` for its sideways day
  snapping, so a horizontal swipe at the last day doesn't trigger browser
  history navigation.

## Goals / Non-Goals

**Goals:**
- Panels as tall as the visible page, with one simple measurement that
  doesn't depend on what is above them.
- Natural nested scrolling: inner panel first, then the page at the
  panel's ends.

**Non-Goals:**
- A sticky toolbar. It would eat into the panel height this change is
  trying to win back.
- Scrolling the page to the panel automatically on load or on a view
  change. Users scroll themselves, so the toolbar is what they see on
  arrival.
- Changing Month view, the list pages, or Day view below `lg`.

## Decisions

### D1. Height = visible page area, not the space left under the toolbar

`useFillHeight` computes:

```
height = max(floor, main.clientHeight − main.paddingTop − bottomGap)
```

- `bottomGap` is read the same way as today (`main`'s side padding, which
  the app-shell spec makes equal to the bottom gap).
- The panel's own top no longer appears in the formula, so the height
  doesn't change when the toolbar wraps, the empty-week notice appears,
  or the page is scrolled.
- Re-measure only on window `resize` and `orientationchange`. A
  `ResizeObserver` on `<main>` itself is safe, since only `main`'s border
  box is observed and the panel doesn't change that. It also catches the
  sidebar drawer or top bar changing `main`'s height without a window
  resize. Use it in place of the `controlsRef` observer.
- Remove `observeRef`/`remeasureKey` from the hook. Remove the
  `controlsRef` wrapper div and `isEmptyRange` plumbing from
  `calendar-page.tsx`, but keep `isEmptyRange` for the notice itself.

*Alternative considered:* keep fit-under-toolbar and only shrink the
toolbar (collapse the filters). That still leaves a 720px window with a
short board, and changes the toolbar UX, which no one asked for.

*Alternative considered:* a fixed CSS height (`h-[calc(100dvh-…)]`). It
would hard-code the top-bar height and page padding, which differ by
breakpoint, and it drifts as soon as either changes. The measured hook
already exists.

### D2. Floor back to 420px at every width

The 240px desktop floor only existed so the board could fit under the
toolbar on short windows. With page scroll allowed, that reason is
gone, and 420px keeps a usable column on very short windows. Use one
constant for both panels.

### D3. Scroll hand-over: drop vertical `overscroll-contain`

- Week column bodies: remove `overscroll-contain`.
- Day card body: remove `lg:overscroll-contain`.
- Keep the board's `overscroll-x-contain`. Sideways hand-over would
  trigger history swipes on trackpads and phones.

With the default `overscroll-behavior: auto`, a wheel or touch gesture
that starts while a body is at its edge scrolls the page instead. That is
the hand-over the spec asks for. In Chromium, a gesture that reaches the
edge mid-way stays on the inner scroller until the gesture ends, so the
hand-over happens on the next gesture. That is standard browser
behaviour, and it's what the spec scenarios ("scrolls again") describe.

### D4. Sticky hour headings and lazy loading are untouched

Both depend on the panel body being the scroll container. That doesn't
change: the body still has `overflow-y-auto` and an explicit-height
parent. `PagedDayList`'s `scrollRootRef` logic (card body from `lg` up,
`<main>` below) stays as it is.

## Risks / Trade-offs

- **[Trade-off]** The toolbar is off-screen while the user works inside a
  full-height board. To change the week or a filter, they scroll back up.
  → Accepted as the request. Hand-over (D3) makes scrolling back up one
  gesture over the panel.
- **[Risk]** Nested scrolling can feel "sticky" in Chromium, where the
  first gesture after hitting a column end does nothing to the page.
  → That's the platform default. Documented in D3, not worked around in
  JS.
- **[Risk]** Several e2e tests assert that `main` doesn't scroll in Week
  or Day view: `test_busy_day_scrolls_inside_its_column`,
  `test_week_board_leaves_the_page_gap_without_scrolling_the_page`,
  `test_week_board_fits_a_laptop_window`,
  `test_day_view_scrolls_inside_its_card`, and the device matrix's
  week/day check. `test_week_column_status_is_in_view_without_scrolling`
  assumes the column footer is on screen with the page at its top. The
  paged-list pagination test is unaffected.
  → Tasks 3.1–3.6 rewrite each one against the new behaviour.

## Migration Plan

Front-end only. Ship with the web build; rollback is reverting the
commit. Archive `fix-paging-footers-and-calendar-day-scroll` before this
change, because this change's delta modifies and removes requirements
that change adds.
