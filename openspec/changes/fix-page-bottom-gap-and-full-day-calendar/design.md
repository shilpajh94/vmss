## Context

**Bottom gap.** `AppShell`'s `<main>` is the only scroller. It carries
`p-page-content` (16/24/32px). Its only child is `RouteTransition`'s
wrapper, which is `h-full min-h-0`: exactly as tall as `<main>`'s content
box. That height is fixed so `PageContentLayout` (`lg:h-full`) can give
fixed-header pages an inner scroll region.

On a page taller than the screen, the content overflows that fixed-height
wrapper. A scroll container adds its end padding after its in-flow
children's boxes, not after their overflow, so `<main>`'s bottom padding
ends up behind the content. The last card then sits flush with the window
edge. The calendar's `WeekBoard` sizes itself in JS as `main.clientHeight
- top - 24`. That ignores the actual bottom padding (32px on desktop), so
the board is a few pixels too tall and nudges the page into scrolling
(see the screenshot in the request).

**Calendar timeline.** `calendar-grouping.ts::groupBySlot` builds groups
only from the loaded visits, so only hours that have visits get a
heading. Visits arrive in the API's standard order: by time, with
any-time visits last. They load 10 (Week) or 20 (Day) at a time through
`useDayPages`. `PagedDayList` renders the groups, then a sentinel and a
progress footer.

## Goals / Non-Goals

**Goals:**
- Fix the bottom gap once, in the shell, so no page needs its own fix.
- Show the 24-hour timeline without changing the paging, the API or
  the refresh behaviour.

**Non-Goals:**
- A proportional time grid (fixed pixel height per hour, events placed by
  minute). A day with 181 visits in one hour can't fit a fixed-height
  slot. The agenda-style timeline keeps every visit readable.
- Per-hour counts from the API, which would let unloaded hours show "N
  visits". That needs an API change. It can be added later without
  changing this layout.
- Changes to Month view.

## Decisions

### D1. The bottom gap is a trailing spacer inside the scrolled content, not `<main>`'s bottom padding

- `<main>` keeps its top and side padding but drops its bottom padding
  (`pb-0`).
- `RouteTransition`'s wrapper gets a final, non-shrinking spacer
  (`after:` pseudo-element, `flex-none`). Its height is the bottom
  padding minus the wrapper's `gap-page-section`, so the visible gap
  equals the page padding at each breakpoint.
- The spacer is part of the wrapper's in-flow content. When a page
  overflows, the spacer overflows with it, so the gap is always there at
  the end of the scroll.
- Fill-height layouts stop using `h-full` and become `flex-1 min-h-0`
  items of the wrapper: `PageContentLayout`'s `lg:h-full lg:min-h-0`
  becomes `lg:flex-1 lg:min-h-0`. They then take the remaining height
  after the spacer and never overflow.

Add the gap tokens as utilities next to `p-page-content` in
`styles/theme.css` (for example `pb-page-end`), so the sizes stay in one
place.

*Alternatives considered:*
- Make the wrapper `min-h-full` / `flex-[1_0_auto]`, so it grows with the
  content and `<main>`'s padding follows it. This breaks
  `PageContentLayout`. Its percentage height resolves against a
  content-sized box, so the inner region stops scrolling.
- Add `pb-*` to each page. This misses new pages and duplicates the
  token.

### D2. `WeekBoard` fills the space with flex, not a hard-coded gap

The calendar page becomes a `flex-1 min-h-0` column inside the wrapper.
From `lg` up, the board is its `flex-1 min-h-0` last child, so it ends at
the spacer from D1 with no measurement.

Below `lg` the page may scroll as a whole, as `PageContentLayout` does,
because the stacked toolbar can be taller than a phone. There the board
keeps its `MIN_BOARD_HEIGHT` (420px) floor via `min-h-[420px]`. If flex
alone can't hold that floor on short landscape phones, keep
`useBoardHeight` but read `<main>`'s spacer height from computed style
instead of `BOTTOM_GAP = 24`. Decide when implementing, by checking the
responsive matrix at 320–414px.

### D3. Timeline is built from 24 fixed slots, then the loaded visits are filled in

A new `buildDayTimeline(events, complete)` in `calendar-grouping.ts`
returns the 24 hour slots (`0`–`23`), each with its loaded visits, then
an `ANY_TIME` slot when it has visits. `groupBySlot` is replaced.
`complete` is `events.length >= total`.

- **Loading frontier.** While `!complete`, the frontier is the slot of
  the last loaded visit. `PagedDayList` renders the sentinel and the
  "Loading more… / Retry / Showing X of Y" row right after that slot's
  visits, inside the frontier slot. Later hour headings render below the
  row.
  - The sentinel sits right after the last loaded visit, so loading
    still triggers when the user nears the end of what's loaded, not the
    end of 24 headings.
  - The spec's "not marked empty" rule holds because no per-hour "no
    visits" text exists, and the progress row visibly sits above the
    later hours.
- If the last loaded visit is any-time, every timed visit is already
  loaded. The frontier is then the "Any time" group, and all 24 hours are
  final.
- **Complete.** When complete, the "All N visits" footer goes after the
  last slot.
- **Empty day.** A day with no visits renders "No visits" above the 24
  headings, replacing today's footer-only message.

*Alternative:* render unloaded later hours collapsed or hidden. Rejected:
the user asked to see the whole day, and hiding them makes the timeline
jump as pages load.

### D4. Compact empty hours, pinned headings

Each slot is a `<section aria-label="10:00 AM">` with the existing sticky
`<h3>`. An empty slot has no `<ul>`, so it takes only the heading's
height, about 24px, or about 580px for an empty day. That is acceptable
in a column that scrolls, and the column opens at the first busy hour
(D5).

Empty hours get a lighter heading style (muted, no backdrop) so busy
hours stand out.

### D5. Open at the first busy hour, once per key

`PagedDayList` takes a `resetKey`: the same `date|branch|statuses` key
`useDayPages` already uses.

- When the key changes and the first page is shown, a layout effect
  scrolls the scroll root so the first slot with visits is at its top.
  The root is the column body in Week. In Day view it is `<main>`, using
  `scrollIntoView({block: 'start'})` and accounting for the sticky
  heading.
- It runs once per key, tracked in a ref. Loading more and refreshes
  don't change the key, so they never move the scroll, as the spec
  requires.
- A day with no timed visits stays at the top.

## Risks / Trade-offs

- **Removing `<main>`'s bottom padding affects every page.** Pages that
  `return` fragments or use `mainClassName` overrides could lose their
  gap or gain a double one. → Audit the `mainClassName` users
  (`grep mainClassName`). Extend `e2e/test_responsive_matrix.py` to
  assert, on every route at every width and in both themes, that `main`
  scrolled to the end has at least the page padding below the last
  element, and that `PageContentLayout` routes don't scroll `main` from
  `lg` up.
- **24 headings make a quiet week taller to scroll.** → Compact empty
  rows (D4) plus open-at-first-busy-hour (D5).
- **Sticky headings stacking:** 24 sticky `<h3>`s in one scroller are
  fine. Each sticks only within its own section. → No change needed;
  covered by the existing sticky behaviour.
- **Auto-scroll fighting the user:** if the first page arrives late, the
  user may already have scrolled. → Skip the auto-scroll if the root's
  `scrollTop` is already non-zero when it would run.

## Migration Plan

Web-only, no API or data changes. Deploy normally. Roll back by
reverting the commit.
