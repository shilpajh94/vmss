## Context

Both boards use `useInvitationsBoard` → `usePagedBoardColumns`, which
calls `fetchPage` (→ `ListVisitRequestsUseCase` →
`HttpVisitRequestSummaryRepository.list`) in three places:
- `fetchWindow`'s single call (first load and keep-depth reload, up to
  100 rows)
- `fetchWindow`'s multi-page call (a reload deeper than 100 rows)
- `loadMore` (scroll)

Each call spreads the caller's `ColumnQuery` and adds `status`, `page`,
and `pageSize`. `HttpVisitRequestSummaryRepository.list` copies an
explicit allow-list of params into the query string, so a new param has
to be added there too. The API side is described in `VMSS_API`
`openspec/changes/sort-invitation-board-by-status-date/`.

## Goals / Non-Goals

**Goals:**
- Every board column request asks for `sortBy=status_changed_at`,
  `sortOrder=desc`, from one place, so a future fetch path can't forget
  it.

**Non-Goals:**
- Showing a "checked in 5 min ago" time on cards. The API's new
  `statusChangedAt` row field is not added to the Zod schema, since
  nothing renders it. Zod drops unknown keys, so it's harmless to ignore.
- A user-selectable sort control.
- Changing the export or any non-board list.

## Decisions

### 1. Set the sort inside `usePagedBoardColumns`, not in `ColumnQuery`

Add a module constant,
`BOARD_SORT = { sortBy: 'status_changed_at', sortOrder: 'desc' } as const`,
and a small `columnPageParams(query, status, page, pageSize)` helper that
all three `fetchPage` call sites use. The order is part of what a "board
column" is, like the status mapping already in this file.
*Alternative considered*: putting it into `columnQuery` in
`useInvitationsBoard`. `ColumnQuery` holds filters and is rebuilt on
every filter change, so the sort would ride along with filter state, and
a new caller of the hook could leave it out.

### 2. Typed params, passed through by the repository

`ListVisitRequestsParams` gains
`sortBy?: 'submitted_at' | 'created_at' | 'status_changed_at'` and
`sortOrder?: 'asc' | 'desc'`, matching the API whitelist and the
`device-repository`/`kiosk-repository` params. The HTTP repository adds
both to its `queryParams` allow-list. `undefined` values are already
dropped there, so other callers are unaffected.

## Risks / Trade-offs

- [The web deploys before the API, so every column gets a 422 and the
  board shows its load-failure state] → release order is API first. The
  tasks include checking that the deployed API accepts the value before
  merging.
- [A keep-depth poll reorders cards under a scrolled user, because a
  check-in moves a card to the top of Checked-in] → this is intended: the
  newest activity rises to the top. The existing de-duplication in
  `appendUnique` still stops any card appearing twice.
