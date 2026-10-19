## Why

On the staff Visits board (and the admin Invitations board, which shares the
same component), the Requested / Approved / Checked-in / Denied column headers
scroll out of view with the cards. Once a column is long, there is no way to
tell which status the cards on screen belong to.

The board also does not scale. It makes one `GET /invitations` call capped at
`pageSize=100`, then splits the result into columns in the browser. That causes
three problems once a tenant has real volume:

- **Silent truncation.** Anything past the 100 most recent invitations never
  appears on the board. A column can look empty when it is not.
- **Wrong counts.** Each header's count is the number of cards loaded, not the
  real total. With 1,000 invitations the badges still add up to at most 100.
- **One detail fetch per card.** For every Requested or Approved card, the board
  also calls `GET /invitations/{id}` up front to show the "Level X/Y" badge. A
  page of 100 cards can mean 100 extra requests.

## What Changes

- **Pinned column headers.** On desktop the board fills the space below the
  search/filter bar. Each column's cards scroll inside that column, and its
  header (label + count) stays visible. Below `lg`, the status selector stays
  pinned above the single visible column.
- **Lazy loading per column.** Each status column loads its own pages from the
  server, 20 cards at a time. When the user scrolls near the bottom of a column,
  the next page loads automatically. A small loading row appears while it loads,
  and an "all loaded" end state appears once there is nothing more.
- **Real totals in the headers.** Each column's count badge (and the count on
  the mobile status tabs) shows the server's total for that status. It no
  longer shows how many cards happen to be loaded.
- **Filters and search move to the server on the staff board too.** Purpose,
  registration type, and search are sent as query parameters on every column's
  request. They no longer filter an already-loaded list in the browser, which
  would only ever filter the loaded pages. This needs a new `purposeOfVisit`
  filter on `GET /invitations`, delivered by the paired API change
  `add-invitation-purpose-filter` in `VMSS_API`.
- **Refresh keeps your place.** Manual refresh, the 15-second background
  refresh, and reloads after approve/deny/reschedule/delegate/edit refetch the
  pages each column has already loaded. A column you scrolled deep into does not
  jump back to the top. A card that changed status leaves its old column and
  shows up in its new one.
- **Detail fetches follow loaded cards.** The "Level X/Y" approval-progress
  preload still runs, but only for cards actually loaded. That is at most 20 new
  detail calls per page, not one per invitation in the result set.
- **Spec wording fix:** the staff dashboard's search requirement said it matches
  host name. The implementation has only ever matched visitor name or REQ ID,
  and server-side search matches the same two fields. The requirement is
  corrected to match what is built.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `staff-dashboard`: column counts come from the server total; columns load
  lazily, 20 at a time; headers stay pinned while cards scroll; search and
  purpose/registration-type filters run on the server; refresh keeps loaded
  pages.
- `admin-invitations`: the same column-count, lazy-loading, and pinned-header
  behaviour as the staff board, which it shares.
- `responsive-layout`: below `lg`, the board's status selector shows server
  totals and stays pinned while the selected column scrolls.

## Impact

- **Code:** `src/presentation/hooks/use-invitations-board.ts` (column state
  changes from one flat list to per-status paged lists; filter handling;
  refresh/polling), `src/presentation/components/invitation-board/KanbanColumn.tsx`
  (scroll container, pinned header, load-more sentinel, end/loading rows),
  `ResponsiveBoard.tsx` (height-bounded layout, pinned tabs, totals),
  `staff-dashboard.tsx` / `admin-invitations.tsx` (board fills the remaining
  height), and `src/data` / `src/infrastructure` visit-request repository
  (`page` + `purposeOfVisit` params; return items and pagination meta, not just
  the array).
- **API dependency:** `GET /invitations?purposeOfVisit=` from
  `add-invitation-purpose-filter` (`VMSS_API`). Everything else the board needs
  (`status`, `search`, `registrationType`, `page`, `pageSize`, `pagination.total`)
  already exists.
- **Requests per load:** four list calls (one per column, 20 rows each), down
  from one call of 100 rows. Detail preloads are capped by what is loaded.
- **No breaking API change.** The purpose filter is an additive, optional
  query param.
