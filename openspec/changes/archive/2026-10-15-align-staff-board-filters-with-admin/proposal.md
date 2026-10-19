## Why

The staff dashboard and the admin Invitations board show the same kanban
board through the same `BoardFilterBar` and `useInvitationsBoard` hook. The
staff bar only exposes Purpose of Visit and Registration Type. The admin bar
also has Status and Source filters, a "Clear filters" action, and a search
placeholder that matches what the search actually does (visitor name or
tracking ID). Staff who work through a busy board can't narrow it to, say,
walk-ins or archived no-shows, and the staff search hint promises
host matching the API doesn't do.

## What Changes

- **Status and Source filters on the staff bar.** These are the admin
  board's Status filter (All statuses, Requested, Approved, Checked-in,
  Checked-out, Denied, Archived) and Source filter (All sources, Staff
  Pre-Registration, Visitor Walk-in), in the same order and from the same
  shared options. Status narrows the board to that one column, as on admin.
  Source is applied on the server to every column.
- **"Clear filters" on the staff bar.** It appears whenever any of the four
  filters differs from its default, resets all four, and keeps the search
  text, as on admin.
- **Search placeholder** becomes "Search visitor, tracking ID...", the
  admin wording. The search behavior itself is unchanged.
- **Export starts from the active Status filter.** The staff Export dialog
  opens with the board's current Status filter preselected, as the admin
  dialog does, instead of always opening on "All statuses". Its "applied
  filters" summary already includes Source.
- **Filtering stays scoped to the staff member's own invitations.** The
  new filters narrow the staff board's existing "relevant to me" results.
  They never widen it to branch-wide invitations.
- **Shared filter state.** `isFiltering` and `clearFilters` move from the
  admin page into `useInvitationsBoard`, so both pages share one definition
  and can't drift apart.
- The admin board's Status filter list in its spec is updated to include
  Archived, which the code already offers since the archived-status change.
- No API change. `GET /invitations` and `GET /invitations/export` already
  accept `status` and `source` together with `relevantToMe=true`.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-dashboard`:
  - "Filters narrow the board by purpose of visit and registration type"
    gains Status and Source, plus "Clear filters".
  - "Search filters visible requests by visitor, host, or REQ ID" is
    corrected to visitor name or tracking ID, with the new placeholder.
  - "The workspace header and search bar are compact" covers four filters.
- `admin-invitations`: "Search and filters sit in one inline bar matching
  the staff dashboard" lists Archived among the Status options.

## Impact

- `src/presentation/pages/staff-dashboard/staff-dashboard.tsx`: pass
  `extraFilters`, `isFiltering`, `onClearFilters` and `searchPlaceholder`
  to `BoardFilterBar`, and `initialStatus={statusFilter}` to
  `ExportInvitationsModal`.
- `src/presentation/hooks/use-invitations-board.ts`: expose `isFiltering`
  and `clearFilters`.
- `src/presentation/pages/admin-invitations/admin-invitations.tsx`: use the
  hook's `isFiltering` and `clearFilters` instead of local copies.
- No new dependencies, no API or contract change, and no change to which
  invitations a staff member can see.
