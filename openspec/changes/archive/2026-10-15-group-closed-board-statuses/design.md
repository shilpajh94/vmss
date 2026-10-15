## Context

See proposal.md (Why). State after `declutter-invitation-board` (implemented,
not yet archived):

- `ResponsiveBoard.tsx` takes `boardKey`, `columns`, and
  `renderColumn(column, { isCollapsed, onToggleCollapse })`. From `lg` up it
  renders every column side by side and stores the collapsed set under
  `vmss:ui:board:<boardKey>:collapsed-columns`. Below `lg` it renders the six
  status tabs.
- `KanbanColumn.tsx` has a header with a collapse chevron and a collapsed
  56px strip mode. Expanded, it is `lg:min-w-[240px] lg:flex-1 lg:basis-0`.
  Its root div owns the drop handlers, and its card list owns the
  infinite-scroll sentinel.
- `use-paged-board-columns.ts` keeps one paged query per status, held in the
  page's hook, so unmounting a column's list loses nothing.
  `use-invitations-board.ts` exports `BOARD_STATUS_COLUMNS` (six statuses)
  and exposes `statusFilter` (an API status string, mapped by
  `boardStatusForApiStatus`).
- `useStoredState` (`hooks/use-stored-state.ts`) already exists for safe,
  flicker-free per-browser preferences.
- Width math for four columns (three 12px gaps, 32px page padding each
  side): 1366px with a 280px sidebar gives ~246px per column. 1280px gives
  ~225px expanded and ~277px with the rail.

## Goals / Non-Goals

**Goals:**
- Desktop grouping lives entirely in the shared board component, so both
  pages get it from one implementation.
- No new data fetching. The switcher only chooses which already-loaded
  status renders.
- Remove every trace of per-column collapse: UI, props, and stored key reads.

**Non-Goals:**
- Arrow-key roving focus in the switcher. The mobile status tabs don't have
  it either, and both should be updated together if it's ever added.
- Deleting stale `collapsed-columns` keys from users' storage. Nothing reads
  them, and no user ever had them, since the feature was never released.

## Decisions

### 1. Closed-status set is data, not hard-coded in the board
Export `CLOSED_BOARD_STATUSES = ['checked_out', 'denied', 'archived']` from
`use-invitations-board.ts`, next to `BOARD_STATUS_COLUMNS`, and pass it to
`ResponsiveBoard` as `closedStatuses`. The board component stays generic
over its column type, as it is today. Both pages pass the same constant.

*Alternative:* hard-code the three statuses inside `ResponsiveBoard`. That
would tie a layout component to domain statuses, which it deliberately
avoids now.

### 2. A dedicated `ClosedStatusesColumn` renders the group
New `invitation-board/ClosedStatusesColumn.tsx`, rendered by
`ResponsiveBoard` after the working columns on desktop:
- **Sizing:** the same as any column (`lg:min-w-[240px] lg:flex-1
  lg:basis-0`), so the 240px floor and even sharing apply unchanged.
- **Header:** matches `KanbanColumn`'s header (accent left border, a neutral
  `text-faint` tint like Checked-out's), with the label "Closed" and the
  summed total.
- **Switcher:** a full-width segmented control, `role="tablist"` with
  `aria-label="Closed status"`. It has three content-sized `role="tab"`
  buttons (`flex-auto`, not equal thirds), each stacking its label over its
  count (11px semibold label, count badge). The selected segment uses that
  status's accent colours. *Revised during implementation:* equal thirds
  truncated the selected "Checked-out" label to "Checked-…" at 1366px with
  the sidebar expanded (~68px per segment). Content-sized segments give it
  the width it needs, and QA confirmed no label truncates at 1280, 1366, or
  1536px.
- **Body:** a `role="tabpanel"` that renders
  `renderColumn(selectedColumn, { embedded: true })`.

`renderColumn`'s second argument becomes `{ embedded: boolean }`, replacing
`ColumnCollapseState`. Working columns and the mobile tabs pass
`embedded: false`.

*Alternative:* fold the switcher into `KanbanColumn`. That would mix a
multi-status container into the single-status column component, the kind
of special-casing the collapse mode already showed is hard to read.

### 3. `KanbanColumn` loses collapse and gains `embedded`
Remove the `isCollapsed`/`onToggleCollapse` props, the strip branch, the
header chevron, and the `!isCollapsed` sentinel gate. Add `embedded?:
boolean`:
- When `true`, it renders no header of its own (the Closed column owns it),
  and its root fills the tab panel (`flex min-h-0 flex-1 flex-col`) instead
  of taking the column sizing classes.
- Everything else is unchanged: the card list, paging, empty state, and
  the drop handlers on the root.

Only the selected closed status is mounted. Unselected statuses therefore
have no sentinel and load no pages. Their data stays in
`usePagedBoardColumns`, so switching back shows already-loaded cards
instantly. The selected list remounts on switch and starts at the top,
which is acceptable for a look-up column. Other columns are untouched, so
they keep their scroll.

### 4. Selection: stored per board, focused by the status filter
`ResponsiveBoard` owns the selection with
`useStoredState('vmss:ui:board:<boardKey>:closed-status', 'checked_out',
parse)`. `parse` only accepts a value in `closedStatuses`. A new optional
prop, `focusClosedStatus?: BoardStatus`, is computed by each page from
`boardStatusForApiStatus(statusFilter)` when it falls in the closed set. An
effect selects (and stores) that status whenever the prop changes to a
closed status.

Storing it is deliberate: the user's latest explicit choice of a closed
status, whether made in the filter or the switcher, is what they expect
next time. The user can still click another segment while the filter is
active. That segment just shows zero, which matches how the working
columns already behave under a status filter.

*Alternative:* make the filter a hard override that disables the other
segments. That adds a disabled state for no real gain, and the working
columns don't do it either.

### 5. Mobile path unchanged
Below `lg`, `ResponsiveBoard` keeps its existing six tabs and calls
`renderColumn(activeColumn, { embedded: false })`. `closedStatuses` and the
stored selection are ignored there.

## Risks / Trade-offs

- [Closed statuses are one click further away than with separate columns]
  → Each count is always visible in the switcher, so nothing is out of
  sight. The status filter jumps straight to a closed status. Users act on
  these statuses rarely (proposal Why).
- [Segment labels could truncate at the 240px floor with larger system font
  settings] → Segments are content-sized, so the longest label gets its
  natural width first. If one still overflows, it truncates with an
  ellipsis, and the tab's accessible name still carries the full label and
  count.
- [Denied is a drop target in the code but is only mounted when selected] →
  Cards currently have no drag source at all (found during
  `declutter-invitation-board` QA), so nothing changes for users. The
  drop handler still works whenever Denied is the selected segment.
- [Spec ordering] → This change REMOVEs requirements that
  `declutter-invitation-board` adds. Archive that change first.
  Implementation order doesn't matter.

## Migration Plan

Frontend-only. Ship with or after `declutter-invitation-board`. A rollback
restores the previous six-column layout. The new `closed-status` key is
harmless if left behind.
