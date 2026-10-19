## Why

The invitation board on the staff dashboard and the admin Invitations
page shows each status column newest first, but by the date the visitor
*submitted* the request, not the date it moved into that column. A
visitor who checked in a minute ago, but submitted last week, sits below
someone who checked in hours ago. The paired API change
(`VMSS_API` `sort-invitation-board-by-status-date`) added
`sortBy=status_changed_at` to `GET /invitations`, which orders rows by when
each invitation entered its current status. That option is opt-in: the
API's default order is unchanged, so the boards keep the old order until
the web asks for the new one.

## What Changes

- Every board column query (Requested, Approved, Checked-in, and each
  Closed tab: Checked-out, Denied, Archived) sends
  `sortBy=status_changed_at&sortOrder=desc`. That covers the first page,
  each scroll-to-load page, and the keep-depth refresh/poll reload. Each
  column then shows the invitation that most recently entered that status
  first.
- This applies to both boards, which share one data hook: the staff
  dashboard (`relevantToMe=true`) and the admin board (organisation-wide).
- The invitation export is not changed. It already orders by the
  status-matched date on the server.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `staff-dashboard`: "Columns load visit requests lazily in pages" now
  defines "most recent" as most recently entered that status, not most
  recently submitted.
- `admin-invitations`: "Invitations board pins its column headers and
  loads columns lazily" gets the same ordering scenario for the admin
  board.

## Impact

- **Code**:
  - `src/data/repositories/visit-request-summary-repository.ts`: add
    `sortBy`/`sortOrder` to `ListVisitRequestsParams`.
  - `src/infrastructure/visit-request-summary-repository.ts`: pass them as
    query params.
  - `src/presentation/hooks/use-paged-board-columns.ts`: set them on every
    column fetch.
- **Dependency**: needs the API change deployed first. An API without it
  rejects `sortBy=status_changed_at` with a 422, and every column fails to
  load. Deploy the API first.
- **No change to**: card layout, filters, export, or any other page that
  lists invitations.
