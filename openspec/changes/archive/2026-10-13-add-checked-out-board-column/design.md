## Context

Both invitation boards (admin `/admin/invitations` and staff/reception `/staff/dashboard`) render from one shared hook, `useInvitationsBoard`. That hook delegates column loading to `usePagedBoardColumns`, where each column is one `GET /invitations?status=<x>` query. The set of columns is hard-coded in three places that must agree:

- `use-paged-board-columns.ts`: `BoardStatus` union, `BOARD_STATUSES`, `API_STATUS_BY_BOARD_STATUS`, and the initial `ColumnsState`.
- `use-invitations-board.ts`: `BOARD_STATUS_COLUMNS`, which gives order and labels and also derives `ALL_BOARD_STATUSES`.
- `KanbanColumn.tsx`: `ACCENT_CLASSES`, whose keys type the `status` prop.

Pages add per-status wiring on top: `EMPTY_MESSAGES`, and the `onDrop`/`onMoveTo*` props, which are only set for `requested`/`approved`/`denied`. `ResponsiveBoard` iterates whatever columns it receives, so the mobile tabs need no change. `VisitRequestCard` gates Reschedule/Edit on `RESCHEDULABLE_STATUSES` and approve/deny on the current approval step, so a `checked_out` card already renders only Visitor Info.

## Goals / Non-Goals

**Goals:**
- Make `checked_out` a first-class board status, the same as the other four, by extending the existing per-status tables. No new loading path.
- Keep the TypeScript `Record<BoardStatus, …>` types exhaustive, so that a missed table fails `tsc -b` rather than producing a column that silently never loads.

**Non-Goals:**
- No API change. The `checked_out` filter already exists.
- Sorting the column by most-recent check-out. `GET /invitations` only sorts by `submitted_at`/`created_at`, so the column uses the same default order as every other column.
- Date-scoping the column (for example "checked out today"). No column is date-scoped today, and adding it would need a new API filter.
- Hiding or collapsing columns, or making the column set configurable per role.

## Decisions

**1. Column position: between Checked-in and Denied.**
This follows the visit lifecycle (requested → approved → checked-in → checked-out), with Denied kept as the terminal off-path column at the far right, where users already expect it. Appending after Denied would read out of sequence.

**2. One server query per column, the same as the other columns.**
`API_STATUS_BY_BOARD_STATUS.checked_out = 'checked_out'`. `boardStatusForApiStatus('checked_out')` then resolves, and that fixes the admin status filter (whose dropdown already lists "Checked-out") with no change to the filter code. The alternative was to fold checked-out into the Checked-in column with a sub-badge. That was rejected because it breaks the "one status = one column = one true total" invariant that the paged-columns design relies on.

**3. Neutral/muted accent.**
`checked_out` gets `border-l-text-faint`, `bg-text-faint/8`, `text-text-muted`, and the matching `dragOver` classes, mirroring the existing `checked_out` pill in `VisitorInfoModal` (`bg-text-faint/15 text-text-muted`). A finished visit should read as inactive, not compete with the actionable columns. The `dragOver` classes are required only because `ACCENT_CLASSES` is keyed exhaustively. The column never receives a drop, because pages don't pass `onDrop` for it.

**4. No new card actions.**
The existing gating already gives Visitor Info only, so nothing in `VisitRequestCard` changes. Pages keep wiring `onDrop`/`onMoveTo*` by explicit status comparison, so `checked_out` falls through to `undefined`.

## Risks / Trade-offs

- **[One more request per load, refresh and poll (5 instead of 4)]** → Each request is page-size-bounded (20 rows, or the loaded depth on keep-depth refresh), and the requests run in parallel inside the existing `Promise.all`. The added cost is one small indexed list query per poll.
- **[Five columns are tight at exactly `lg` (1024px)]** → The desktop board container is already `overflow-x-auto` and columns are `flex-1 min-w-0`. Verify at 1024px and 1280px that card buttons don't wrap badly. If they do, give columns a minimum width so the board scrolls horizontally instead of squeezing.
- **[Unbounded column total]** → Checked-out grows without limit, the same as Denied. Paging keeps the DOM bounded. The badge count growing is accurate, not a bug.
- **[A visitor who re-enters moves back to Checked-in]** → This is correct under allow-multiple-checkins (`checked_out` → `checked_in` cycles). The card moves between columns on the next poll. No special handling is needed.

## Migration Plan

This is a frontend-only, additive change, deployed with the next web release. Rollback is reverting the commit. There is no data or API dependency.

## Open Questions

- Should the Checked-out column later sort by most-recent check-out first? That needs `checked_out_at` added to the API's `InvitationSortableField` whitelist. It is deferrable and changes neither this spec nor these tasks.
