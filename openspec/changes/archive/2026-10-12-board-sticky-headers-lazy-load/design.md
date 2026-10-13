## Context

Both boards (staff `/staff/dashboard`, admin `/admin/invitations`) are built on
`useInvitationsBoard` (`src/presentation/hooks/use-invitations-board.ts`),
`ResponsiveBoard`, and `KanbanColumn`. How it works today:

- `loadDashboard` makes **one** `listVisitRequestsUseCase.execute(params)` call.
  `HttpVisitRequestSummaryRepository.list` sends `pageSize: 100` and returns
  only `response.data`, so the pagination metadata is thrown away.
- `columns` is a `useMemo` that splits that single array by
  `resolveEffectiveStatus`. Each `KanbanColumn` shows `requests.length` as its
  count.
- The staff board runs in "client mode": search, purpose, and registration
  type filter the loaded array in memory. The admin board runs in
  `serverFilters` mode: search, status, registration type, and source go to
  the API, but it is still a single page of 100.
- A preload effect calls `getInvitationDetailUseCase` for every loaded card
  whose status is `requested`/`approved`. This is for the "Level X/Y" badge and
  for `resolveEffectiveStatus`'s "approved but a step is still pending → keep in
  Requested" remap.
- `AppShell`'s `<main>` is `overflow-y-auto`, so the whole page scrolls,
  headers included.
- API facts this design relies on (`VMSS_API`):
  - `GET /invitations` already supports `status`, `search`, `registrationType`,
    `source`, `page`, `pageSize` (max 100), and returns `pagination.total`.
  - `get_current_approval_step` returns `None` unless the invitation's status is
    `submitted`. In other words, an invitation stays `submitted` until its last
    approval step clears, and the API never returns an `approved` row with a
    pending step.
  - There is no purpose filter. The paired change
    `add-invitation-purpose-filter` adds one.

## Goals / Non-Goals

**Goals:**
- Column headers (and the mobile status tabs) never scroll out of view.
- The number of rows fetched and rendered scales with what the user scrolls
  through, not with the tenant's total invitation count.
- Header counts are true totals.

**Non-Goals:**
- List virtualization (`react-window` or similar). With a page size of 20, a
  user would have to scroll past several hundred cards in one column before DOM
  size becomes a real cost. That is not a realistic triage pattern. Revisit only
  if profiling shows it.
- Adding `currentApprovalStep` to `GET /invitations` list rows to remove the
  per-card detail preload. That is a worthwhile API follow-up, but lazy loading
  already caps the preload at 20 per page. See Risks.
- Cursor pagination. `api-conventions.md` §1 settles on limit/offset, and
  duplicate handling below covers its one weakness here.
- Changing what the Checked-in column contains (for example, today only). Its
  empty-state copy says "today", but no date filter exists today. That is
  out of scope.

## Decisions

### 1. One server query per column, not one shared query split in the browser

Each of the four columns gets its own paged query: `status=<column status>` plus
the shared filters, `page`, and `pageSize=20`. The column's count badge is that
query's `pagination.total`.

*Why:* this is the only way counts are true and no column is starved. A single
shared, paged query sorted by `submittedAt` would fill 20 slots with whatever
statuses are newest. A column whose items are older could stay empty until the
user paged far enough in some other column.

*Mapping:* `requested → submitted`, `approved → approved`,
`checked_in → checked_in`, `denied → denied` (the inverse of `STATUS_ALIASES`).

*Admin status filter:* if `statusFilter` is set, only the matching column runs
its query. The other three are set to `{items: [], total: 0, done: true}`
without a request.

*Alternative considered:* add a grouped-count endpoint and keep one list query.
Rejected. It still starves columns, and it needs a new API endpoint for no gain.

### 2. Drop the `resolveEffectiveStatus` remap

Per Context, the API keeps a mid-workflow invitation as `submitted`, so it
already arrives in the Requested column's query. The remap would now cause harm:
it would move a card out of the column whose `total` counted it. The count would
then disagree with the cards shown.

The detail preload stays, because the "Level X/Y" badge still needs it. But it
no longer decides which column a card goes in.

*Verified (task 1.1):* in `VMSS_API`, `approvals/service.py::approve_step`
only calls `invitations_service.approve_invitation` (the sole `submitted →
approved` write) once `get_current_pending` returns `None`. A middle step
instead activates the next step and leaves the invitation `submitted`. The plain
`approve_invitation` path returns 409 while any step is still pending. So no
code path produces `approved` with a pending step.

### 3. Column state shape and the paging hook

The flat `visitRequests` array is replaced by per-column state:

```ts
type ColumnPage = {
  items: VisitRequestSummary[]
  total: number
  loadedPages: number   // highest page fetched
  isLoadingMore: boolean
  loadMoreError?: string
  hasMore: boolean      // items.length < total
}
```

The state lives in a reducer (or a small `usePagedColumns` helper) inside
`useInvitationsBoard`. It exposes `loadMore(status)` and `reloadAll({ keepDepth })`.

The repository's `list()` becomes
`list(params): Promise<{ items; pagination }>`. Its callers today are just this
hook, so this is not a breaking change outside the module. The request params
gain `page` and `purposeOfVisit`.

*Deduplication:* appending page N filters out any `id` already in `items`.
Offset paging over a `submittedAt desc` list shifts by one whenever a new
invitation arrives between page loads, so without this the boundary row would
show twice. The opposite case, a row skipped because one moved out, is caught by
the next refresh (Decision 5).

`total` is updated from every page response, so it tracks arrivals and
departures.

### 4. Staff board moves to server filters

`useStaffDashboard` switches to `useInvitationsBoard('/staff/login', 'mine', { serverFilters: true })`.
Purpose is sent as `purposeOfVisit`. The client-mode branch of
`filteredRequests` and `clientModeParams` is deleted. With paged columns,
filtering in the browser would only ever filter the loaded pages, which is
wrong.

*Purpose values (found during apply):* the dropdown's
`PURPOSE_OF_VISIT_OPTIONS` values are slugs (`interview`), but invitations
store the purpose's display name ("Interview"). That's what both wizards
write, from the form-builder `purpose_of_visit` field's options. The old
in-browser filter compared slug to name and so never matched. The dropdown now
sends the label. Two known gaps are left as follow-ups:
- Tenant-configured purposes that aren't in the hard-coded list (e.g.
  "Maintenance / Repair") can't be picked. Fixing that needs a staff-facing
  purpose catalog endpoint.
- `EditInvitationModal` still writes the slug, which produced at least one
  `business-meeting` row in dev data.

Search stays debounced (300 ms, existing `useDebouncedValue`). Any change to the
debounced search or a filter calls `reloadAll({ keepDepth: false })`, which
resets every column to page 1 and scrolls each column back to the top.

### 5. Refresh and polling keep the loaded depth

Manual refresh, the 15 s `usePolling` tick, and the reload after an action
(approve, deny, reschedule, delegate, edit, approve-and-delegate) all call
`reloadAll({ keepDepth: true })`.

For each column, this fetches one request with `page=1` and
`pageSize = clamp(loadedPages × 20, 20, 100)`, then **replaces** the column's
items. One request per column, not one per loaded page. A card that changed
status drops out of its old column and appears in its new one, because each
column is re-queried by status.

If a column has loaded more than 100 rows, the refresh instead fetches pages
1..k at `pageSize=100` in parallel. This is rare and bounded by how far a human
has scrolled.

The polling `isBusy` guard stays as is. Polling also skips a column that has
`isLoadingMore` in flight, so a poll response can't overwrite a just-appended
page.

Replacing items in place keeps React keys (`request.id`) stable, so the scroll
position inside a column is preserved without manual save/restore.

### 6. Layout: height-bounded board, each column its own scroll area

The whole `<main>` currently scrolls. The change is:

- The board page (`staff-dashboard.tsx`, `admin-invitations.tsx`) uses
  `flex min-h-0 flex-1 flex-col`. `ResponsiveBoard`'s desktop wrapper changes
  from `items-start` to `min-h-0 flex-1 items-stretch`, so the board fills the
  height left under the header and the search bar.
- `KanbanColumn` becomes `flex min-h-0 flex-col`. The header is a fixed
  (non-scrolling) row, and the card list is `min-h-0 flex-1 overflow-y-auto`.
  Each column scrolls independently, and its header is structurally always
  visible. No `position: sticky` is needed on desktop.
- Below `lg` (one column at a time), the selected column's list scrolls inside
  the same bounded area, so the status tablist sits above it and never scrolls
  away. That satisfies the responsive-layout delta.

*Alternative considered:* keep the shared page scroll and make headers
`position: sticky; top: 0`. Rejected for two reasons:

- Scrolling one long column would push the other three columns' cards off
  screen.
- Lazy loading would need one shared `IntersectionObserver` root with four
  sentinels racing on the same scroll. Independent scroll areas match how
  Jira and Trello boards behave and give each column its own natural observer
  root.

*Small-height check:* this relies on `AppShell`'s `h-dvh` outer wrapper, which
already exists. On a short landscape phone, the search/filter bar plus tabs must
still leave the list usable. The responsive-layout 360px check covers this (task
5.3).

### 7. Load-more trigger: IntersectionObserver sentinel

A zero-height sentinel `<div>` goes after the last card. An `IntersectionObserver`
watches it, with `root` set to the column's scroll element and
`rootMargin: '0px 0px 200px 0px'` so the next page starts loading before the
user reaches the bottom.

When the sentinel intersects, `hasMore && !isLoadingMore && !loadMoreError` is
true, and the board is not doing a full reload, the column calls `loadMore`.

The column's end shows one of three things:
- a spinner row while loading
- a retry button when `loadMoreError` is set
- a subtle "All N shown" line when the column is fully loaded and longer than
  one page

A small `useInfiniteScrollSentinel(ref, rootRef, onReach, enabled)` hook keeps
the observer logic out of the JSX.

Not a scroll-event handler with `scrollTop` arithmetic: an observer has no
per-frame cost and works the same for mouse wheel, touch, and keyboard.

### 8. Drag-and-drop still works across scroll areas

Native HTML5 drag events (`onDragOver`/`onDrop` on the column wrapper) are
unaffected by `overflow` on the inner list. The drop handler is on the outer
column `div`, which still spans the full column height. No change is needed
beyond keeping the handlers on the outer element.

## Risks / Trade-offs

- **[Risk]** Four list calls per load and per 15 s poll, instead of one.
  → Each call is a small indexed query (20 rows by default). The total payload
  is similar to today's 100-row call. This is acceptable for one board view,
  and the existing `isBusy` guard still applies. (`usePolling` has no
  hidden-tab pause today; adding one is a separate, cross-page concern.)
- **[Risk]** The detail preload is still one `GET /invitations/{id}` per loaded
  Requested/Approved card (`query-performance.md` §2's loop-and-query shape,
  just on the client). → It is now capped at 20 per page scrolled. Follow-up:
  return a `currentApprovalStep` summary on list rows via one batched query in
  the API, then delete the preload. Not done here, to keep the change focused.
- **[Risk]** Offset paging can skip a row when one leaves a column between page
  loads. → The row reappears on the next refresh or poll (≤ 15 s), because
  refresh re-queries the whole loaded window (Decision 5).
- **[Risk]** Removing `resolveEffectiveStatus` is wrong if some API path does
  write `approved` while a step is still pending. → Task 1.1 checks this before
  removal. If it turns out to be wrong, the fix belongs in the API's status
  write, not in a client remap that breaks counts.
- **[Trade-off]** Search no longer matches host name. It never did in the code
  (only in spec text), and the spec delta corrects the text. If host-name
  search is wanted, it needs a server-side join on the host and a separate
  change.

## Migration Plan

The web change depends on `add-invitation-purpose-filter` being deployed first.
Until then, `?purposeOfVisit=` would be ignored by the API (FastAPI drops unknown
query params), so the purpose filter would show unfiltered results. Deploy order:
API first, then web. Rollback is a plain web revert. There is no data or contract
migration.
