## 1. Remove per-column collapse

- [x] 1.1 In `KanbanColumn.tsx`, delete the `isCollapsed`/`onToggleCollapse`
      props, the collapsed-strip branch, the header chevron button, and the
      `!isCollapsed` gate on the infinite-scroll sentinel; drop the now-unused
      `ChevronLeftIcon` import — design.md Decision 3.
- [x] 1.2 In `ResponsiveBoard.tsx`, delete the `collapsed-columns` stored state,
      `toggleCollapsed`, `ColumnCollapseState`, and `NOT_COLLAPSIBLE`.
- [x] 1.3 Remove the `isCollapsed`/`onToggleCollapse` forwarding from
      `staff-dashboard.tsx` and `admin-invitations.tsx`.

## 2. Closed column

- [x] 2.1 Export `CLOSED_BOARD_STATUSES` (`checked_out`, `denied`, `archived`)
      from `hooks/use-invitations-board.ts` beside `BOARD_STATUS_COLUMNS` —
      Decision 1.
- [x] 2.2 Add `embedded?: boolean` to `KanbanColumn`: no header, root fills
      its parent (`flex min-h-0 flex-1 flex-col`) instead of the column sizing
      classes; drop handlers, paging, empty state unchanged — Decision 3.
- [x] 2.3 Build `invitation-board/ClosedStatusesColumn.tsx`: column sizing as
      any column, "Closed" header with summed total, `tablist`
      ("Closed status") of three content-sized tabs stacking label over count with the
      selected status's accent colours, and a `tabpanel` rendering the
      selected status — Decision 2.
- [x] 2.4 Extend `ResponsiveBoard`: `closedStatuses` and optional
      `focusClosedStatus` props; `renderColumn(column, { embedded })`; on
      desktop render working columns then `ClosedStatusesColumn`; selection via
      `useStoredState('vmss:ui:board:<boardKey>:closed-status', 'checked_out',
      …)` accepting only closed statuses, plus an effect that selects (and
      stores) `focusClosedStatus` when it changes; mobile tabs unchanged with
      `embedded: false` — Decisions 4–5.
- [x] 2.5 Wire both pages: pass `closedStatuses={CLOSED_BOARD_STATUSES}`,
      `focusClosedStatus` derived from the hook's `statusFilter` via
      `boardStatusForApiStatus` (only when it is a closed status), and forward
      `embedded` to `KanbanColumn`.
      Derived once in `use-invitations-board.ts` (returned as
      `focusClosedStatus`) rather than in each page, since both pages share
      that hook.

## 3. Verification

- [x] 3.1 `npm run lint`, `npx tsc -b`, and `npm run build` clean.
- [x] 3.2 Playwright QA (staff/reception + admin) at 1920, 1366, 1280px with
      the sidebar expanded and collapsed: four columns; no column toggles
      anywhere; ≥240px columns; no board scroll at 1366 expanded or 1280 with
      the rail; board (not page) scrolls at 1280 expanded.
- [x] 3.3 Closed column: header total = sum of the three counts; default
      Checked-out on first visit; switching to Denied/Archived shows their
      cards and actions (Denied: Visitor info only; Archived: reschedule/edit
      available) without new `/invitations` requests and without moving other
      columns' scroll; selection persists across reload; admin and staff
      remember independently.
- [x] 3.4 Status filter = Denied → Closed selects Denied, other closed counts
      0; clearing the filter keeps Denied selected (it was stored).
- [x] 3.5 390/800px: six status tabs unchanged, no Closed grouping.
- [x] 3.6 Blocked storage: renders with Checked-out selected and switching
      works in memory, no page errors.
- [x] 3.7 Before archiving this change, archive `declutter-invitation-board`
      (its ADDED requirements are what this change REMOVEs), then run
      `openspec validate group-closed-board-statuses --strict`.
