## 1. Preconditions

- [x] 1.1 Confirm against the API (code read of `approvals`/`invitations` status writes plus one manual approve-and-delegate on a 2-step workflow) that a mid-workflow invitation stays `status = submitted` until its last step clears; record the result in design.md Decision 2 before removing `resolveEffectiveStatus`
- [x] 1.2 Confirm `add-invitation-purpose-filter` (VMSS_API) is merged/deployed to the target environment, or plan to ship this change after it — implemented in VMSS_API in the same session (uncommitted); ship it first

## 2. Data layer

- [x] 2.1 Add `page` and `purposeOfVisit` to `ListVisitRequestsParams` (`src/data/repositories/visit-request-summary-repository.ts`)
- [x] 2.2 Change `VisitRequestSummaryRepository.list` to return `{ items, pagination: { page, pageSize, total, totalPages } }` and update `HttpVisitRequestSummaryRepository.list` to send `page`/`purposeOfVisit`, default `pageSize` to 20, and parse/return the pagination meta instead of discarding it
- [x] 2.3 Update `list-visit-requests` use case and its type to the new return shape

## 3. Board state (`use-invitations-board.ts`)

- [x] 3.1 Replace the flat `visitRequests` state with per-column `ColumnPage` state (items, total, loadedPages, isLoadingMore, loadMoreError, hasMore) keyed by board status, with a board-status → API-status map (`requested → submitted`, etc.)
- [x] 3.2 Implement initial load: one `list` call per column (`status`, shared filters, `page=1`, `pageSize=20`) in parallel alongside current user/roles/employees; when admin `statusFilter` is set, query only that column and set the others to empty/done
- [x] 3.3 Implement `loadMore(status)`: fetch `loadedPages + 1`, append with id-dedup, update `total`/`hasMore`; on failure set `loadMoreError` and keep existing items
- [x] 3.4 Implement `reloadAll({ keepDepth })`: keepDepth=false resets every column to page 1; keepDepth=true refetches `page=1, pageSize=clamp(loadedPages×20, 20, 100)` per column (or pages 1..k at 100 when >100 loaded) and replaces items
- [x] 3.5 Wire manual `refresh`, the `usePolling` tick, and every post-action reload (approve, deny, reschedule, delegate, edit, approve-and-delegate) to `reloadAll({ keepDepth: true })`; skip a column with `isLoadingMore` in flight during a poll
- [x] 3.6 Trigger `reloadAll({ keepDepth: false })` when debounced search, purpose, registration type, status, or source filter changes
- [x] 3.7 Remove `clientModeParams`, the client-side `filteredRequests` branch, and `resolveEffectiveStatus` (per 1.1); build `columns` directly from column state, exposing `total`, `hasMore`, `isLoadingMore`, `loadMoreError`, `onLoadMore`
- [x] 3.8 Point the approval-progress detail preload at the union of loaded column items (still requested/approved only) so it runs only for loaded cards
- [x] 3.9 Switch `use-staff-dashboard.ts` to `serverFilters: true` and send `purposeOfVisit` (omit when "all"); remove the now-unused `serverFilters` option if both callers pass true — done by removing the option: the hook is now server-filtered for both callers

## 4. Components and layout

- [x] 4.1 Add `useInfiniteScrollSentinel` hook (IntersectionObserver, root = column scroll element, `rootMargin` 200px bottom, enabled flag)
- [x] 4.2 `KanbanColumn`: outer `flex min-h-0 flex-col` keeps drag/drop handlers; header row non-scrolling showing `total`; card list `min-h-0 flex-1 overflow-y-auto`; append sentinel, loading row, retry button on `loadMoreError`, and "All N shown" end line when fully loaded and longer than one page
- [x] 4.3 `ResponsiveBoard`: desktop wrapper `min-h-0 flex-1 items-stretch`; mobile layout keeps the tablist above a `min-h-0 flex-1` column so it never scrolls away; tab counts use `total`; `BoardColumn` type gains `total`
- [x] 4.4 `staff-dashboard.tsx` and `admin-invitations.tsx`: make the board region `flex min-h-0 flex-1 flex-col` so it fills the height below the header/filter bar (check `AppShell` `mainClassName` usage so `<main>` itself no longer scrolls the board away)
- [x] 4.5 Keep the empty state for columns with `total === 0`, and show the full-board `LoadingState` only on the initial / filter-reset load, never on load-more or polling

## 5. Verification

- [x] 5.1 `npm run lint` and `npm run build` clean — build clean; lint has 0 errors (2 pre-existing warnings in `use-visitor-request-wizard.ts`)
- [x] 5.2 Seed a tenant with ≥250 Requested and ≥50 Approved invitations (API `scripts/seed_dev_data.py` or a one-off script) and manually verify on the staff board at 1280px: headers stay put, counts show 250/50, scrolling Requested loads 20 at a time with a loading row, no duplicate cards, end line shows when fully loaded — verified via Playwright against a throwaway `boardqa` tenant (370 invitations: 260/55/25/30): counts 260/55/25/30, 20→40→60 on scroll, header fixed, no duplicates, Checked-in stops at 25 with "All 25 shown"
- [x] 5.3 Verify at 375px and 360px: status tabs stay visible while the column scrolls, tab counts are totals, switching tabs keeps each column's loaded pages — verified at 375/360/800px: tab counts are totals, tabs stick flush under the top bar (fixed a 16px see-through strip found here), tab switch keeps loaded pages, no horizontal scroll
- [x] 5.4 Verify refresh and a 15 s poll after scrolling to 60 cards keep depth and scroll position; approve a card and confirm it moves Requested → Approved with both counts updating — refresh and a 15s poll kept 60 cards and scrollTop; approving INV-QA00050 moved it Requested→Approved with counts 259/56
- [x] 5.5 Verify search, purpose, and registration-type filters each reset every column to page 1 and that counts match the filtered totals; verify the admin status filter loads only one column — search 10/10 and scroll reset; purpose "Interview" 44/9/4/5; type "Group" 52; admin status filter → 0/56/0/0. Found the purpose slug-vs-label mismatch here (see design.md Decision 4)
- [x] 5.6 Verify drag-and-drop from a scrolled Requested column onto Approved/Denied still works — N/A as worded: cards are no longer draggable (moving uses the card's Approve/Deny buttons); verified approve from a scrolled column instead, depth kept
- [x] 5.7 Simulate a failed load-more (block the request in DevTools) and confirm loaded cards stay and the retry control recovers — aborted page 2 → Retry shown with 20 cards kept; retry loaded 40
- [x] 5.8 Refresh `screenshots.local` for the staff dashboard and admin invitations pages via `npm run screenshots` — ran against the QA admin; output in gitignored `screenshots.local/`
