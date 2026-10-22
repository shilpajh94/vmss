## 1. Shared filter state and options

- [x] 1.1 In `src/presentation/hooks/use-invitations-board.ts`:
  - Add `isFiltering`, which is true when purpose ≠ `'all'`, status ≠ `''`, registration type ≠ `'all'` or source ≠ `''`.
  - Add `clearFilters`, which resets all four filters and leaves the search untouched.
  - Return both from the hook.
- [x] 1.2 Add a shared helper next to `filter-options.ts` that builds the Status/Source `BoardExtraFilter[]` (icons, `STATUS_FILTER_OPTIONS`/`SOURCE_FILTER_OPTIONS`, aria labels) from values and setters.
- [x] 1.3 Admin page (`admin-invitations.tsx`): remove the local `isFiltering`/`clearFilters`, use the hook's versions, and build `extraFilters` with the 1.2 helper. Behavior must stay unchanged.

## 2. Staff dashboard

- [x] 2.1 In `staff-dashboard.tsx`, pass these to `BoardFilterBar`:
  - `extraFilters` from the 1.2 helper;
  - `isFiltering` and `onClearFilters={clearFilters}`;
  - `searchPlaceholder="Search visitor, tracking ID..."`.
  Keep the Export button as `trailingAction`.
- [x] 2.2 Pass `initialStatus={statusFilter}` to the staff `ExportInvitationsModal`.

## 3. Verify

- [x] 3.1 Run `npx tsc -b` and `npm run lint`. Both must be clean apart from pre-existing warnings. Do not run prettier.
- [x] 3.2 Browser check of the staff dashboard as a host and as Reception against local data:
  - Status `Archived` shows only that column.
  - Source `Visitor Walk-in` narrows every column.
  - "Clear filters" appears and resets all four filters while keeping the search.
  - Export opens on the selected status.
  - Layout holds at 1440px, at 1024px (with Clear filters and Export shown) and at 360px with no horizontal scroll.
- [x] 3.3 Re-check the admin Invitations board: its filters and Clear filters work as before.
