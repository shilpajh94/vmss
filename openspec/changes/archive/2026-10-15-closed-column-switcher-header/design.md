## Context

See proposal.md (Why). `ClosedStatusesColumn.tsx` currently renders three
pieces in a `gap-2` column:

- A "Closed" header: `rounded-[10px] border-l-4 px-4 py-2`, Checked-out's
  neutral accent, and a summed-total badge. It measures 40px tall, the same
  as `KanbanColumn`'s header.
- A `role="tablist"` switcher, about 54.5px tall: `p-1` container,
  `flex-auto` segments with `py-1.5`, an 11px label stacked over a 12px
  count.
- The `tabpanel` with the embedded `KanbanColumn`.

Other columns use `gap-3` between header and list. Measured text widths
(Geist, semibold): "Checked-out" is 76px at 12px, "Denied" 41px, "Archived"
53px, so a single-row "label count" switcher needs about 250px before
padding. The column floor is 240px, and it renders at 246px at 1366px with
the sidebar expanded.

## Goals / Non-Goals

**Goals:**
- The switcher is the header: same slot, same 40px height, same visual
  language as the other column headers.
- The first card lines up across all four columns.
- No truncated labels at any board width (240px floor upward).

**Non-Goals:**
- Any behaviour change: selection, storage, filter focus, paging, and the
  mobile tabs are untouched.
- Restyling the other columns' headers.

## Decisions

### 1. Keep stacked segments, compressed to exactly 40px
The tablist container becomes the header box: `h-10`, `rounded-[10px]`,
`border-l-4`, `p-[3px]`, `flex gap-[3px]`. Segments stay `flex-auto
min-w-0` (content-sized, as revised in `group-closed-board-statuses`). Each
uses `py-1` and two lines with `leading-[13px]`: an 11px semibold label
over an 11px bold count. That makes 3 + 4 + 13 + 13 + 4 + 3 = 40px.

*Alternative:* a single row, "Checked-out 2". It matches the other headers'
"label + badge" pattern more closely, but it doesn't fit at 240–246px
(about 250px of text alone), so the most important label would truncate on
common laptops.

*Alternative:* raise every column header to the switcher's 54px. That
wastes height on three columns to suit one.

### 2. Header styling follows the selected status
The left border and the box tint use the selected status's
`ACCENT_CLASSES` (`border`, `tint`), so the header reads like that status's
own column header: blue-grey for Checked-out, red for Denied, amber for
Archived. The selected segment is a raised `bg-surface shadow-sm` chip with
the label in `text-text` and the count in the accent `text`. Unselected
segments are `text-text-muted` with a hover wash. The accent colour moves
with the selection, which is the visual cue for which status is listed.

*Alternative:* a fixed neutral accent. That loses the colour cue the other
columns give, and the Denied red is a useful signal.

### 3. Remove the title row and total; match the column gap
Delete the "Closed" header element, `grandTotal`, and the fixed
`headerAccent`. Change the column's `gap-2` to `gap-3`, matching
`KanbanColumn`, so the tab panel starts at the same offset as the other
columns' lists. The tablist keeps `aria-label="Closed status"`, which is now
the column's only name for assistive technology. Each tab's accessible
name stays "<label>, <count>".

## Risks / Trade-offs

- [11px stacked text is small] → It's the same size the switcher uses
  today and that users have already seen. The counts were 12px and drop to
  11px to fit the height.
- [Larger browser font settings could push the content past 40px] → The
  header uses `h-10` with the segments centred, so the box stays aligned.
  Text may tighten, but the layout can't shift the card lists. This is
  acceptable, since the other headers have the same exposure.
- [Spec ordering] → This modifies a requirement that only exists once
  `group-closed-board-statuses` is archived. See proposal Impact for the
  archive order.

## Migration Plan

A single-component visual change with no stored-state changes. A rollback
restores the two-row header.
