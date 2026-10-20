## Context

See proposal.md for the failure list. Evidence is from the full run on
2026-10-20 (Tue). It was run at the default e2e viewport of 1440×900, after
commit `d2bdc1e`. `test_staff_invitation_lifecycle` passed on a solo rerun.
The other failures are deterministic on this date and with this data.

## Goals / Non-Goals

**Goals:** a full `npm run e2e` with 0 failures, plus clean `npm run lint`
and `npm run build`. Tests should keep passing on other dates and as QA data
builds up.

**Non-Goals:** the "column opens at the first busy hour" rule. It is in the
specs of `fix-page-bottom-gap-and-full-day-calendar` and
`calendar-working-hours-and-roomier-week`, but no code implements it today.
This change only resets to the top (D2) and doesn't build that rule. No
test is deleted or xfailed to get to green.

## Decisions

### D1. The end-gap spacer always has height

Today the bottom gap is `gap-page-section` (16/24px) plus an
`h-page-end-gap` spacer that is 0px below 64rem and 8px from 64rem.
Chromium's scrollable overflow skips the zero-height spacer, so below 64rem
the flex gap before it falls outside the scroll range.

Fix: make the spacer as tall as the full page padding (16/24/32px) and give
it a negative top margin equal to the section gap (16/24/24px). The total
stays 16/24/32px, the box is never zero-height, and nothing changes from
64rem up (32 − 24 = 8, same as now).

Alternative considered: `min-height: 1px` with the gap reduced by 1px. It
works, but a 1px offset is a magic number that drifts if the gap tokens
change.

The first apply task checks the cause with a quick probe (give the spacer
1px at 390px and read `endGap`) before changing the utility.

### D2. Column and day list scroll to the top on a new day, branch or filter key

`useDayPages` already computes a `key` (date|branch|statuses) and resets
its events when the key changes. The scroll container (the week column
body, or `<main>` for the Day list) isn't reset. Reset `scrollTop` to 0 in
the component that owns the scroller, in a layout effect keyed on the same
inputs, so it lands before the sentinel's IntersectionObserver fires. A
refresh (same key) must not move the scroll. That's the spec's "loading
more or a refresh SHALL NOT change the scroll position", and
`test_refresh_keeps_loaded_visits_and_scroll_position` guards it.

Alternative considered: remount the column with `key={...statuses}`. It's
simpler, but it also throws away the column's other state and would remount
all seven columns' observers on every filter tap.

### D3. Week tests bring their column into view

Add a `_show_column(page, day)` helper. It scrolls the board
(`div.snap-x`) sideways so the column's left edge is at the board's left
edge, the same sum `WeekBoard` uses for today. Call it in tests that assert
viewport visibility of a specific column. Don't pin the browser clock
instead: that would hide the "opens at today's column" behaviour the other
tests rely on.

### D4. The timeline week test loads its column to the end

Before asserting the 23:15 visit, scroll the column body to the end until
`All N visits` (or no "Loading more…") shows. It reuses the
`_scroll_column_to_end` / `_settled_count` loop. Keep the seeded day. Don't
add data cleanup to the API: other tests also read QA data that has built
up.

### D5. The lifecycle test waits for the approval to finish

After clicking "Approve Request", `expect(dialog).to_be_hidden()` before
the API read, matching how the reception step already waits.

## Risks / Trade-offs

- [D1 changes spacing on every staff/admin page] → The totals are the same
  by construction. The responsive matrix (all routes, 10 widths, 2 themes)
  is exactly the check for it.
- [The D1 hypothesis is wrong] → The probe task runs first. If the spacer
  height doesn't change `endGap`, the cause is different and design D1 is
  revised before going further.
- [D2 fights the browser's scroll anchoring] → Resetting to 0 is absolute
  and happens in a layout effect after the reset render, so anchoring has
  nothing to keep.
- [The full e2e pass takes ~40 min and shares Redis rate limits with API
  pytest] → Never run it alongside pytest. During fixing, run single
  files, and do one full pass at the end.
