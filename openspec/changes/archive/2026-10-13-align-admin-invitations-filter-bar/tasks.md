## 1. Shared filter bar

- [x] 1.1 Move `src/presentation/pages/staff-dashboard/Components/SearchActionBar.tsx` to `src/presentation/components/invitation-board/BoardFilterBar.tsx`, renaming the component to `BoardFilterBar`, and update the import in `staff-dashboard.tsx`.
- [x] 1.2 Add optional `extraFilters` to `BoardFilterBar` (each `{ icon, value, options, onChange, ariaLabel }`, rendered as `DropdownFilter`s after Registration Type), and optional `onClearFilters` + `isFiltering` (renders an inline "Clear filters" text button when filtering).
- [x] 1.3 Use `xl:flex-nowrap` instead of `lg:flex-nowrap` when `extraFilters` is non-empty, so the staff layout is unchanged.

## 2. Admin Invitations page

- [x] 2.1 In `admin-invitations.tsx`, remove the pill search, the "Filters" toggle button, `isFilterPanelOpen`, the `SelectField` panel, and any imports left unused.
- [x] 2.2 Render `BoardFilterBar` under the "Invitations" title. Pass:
  - `search`
  - Purpose (`purposeFilter`/`purposeOptions` from the hook)
  - Registration Type
  - `extraFilters`: Status (`CircleDotIcon`, "All statuses" + `STATUS_OPTIONS`) and Source (`ClipboardListIcon`, "All sources" + `SOURCE_OPTIONS`)
- [x] 2.3 Extend `isFiltering` to include `purposeFilter !== 'all'`, and make `clearFilters` also reset purpose to `'all'`. Leave the search text untouched.

## 3. Verification

- [x] 3.1 `npm run build` and `npm run lint` pass.
- [x] 3.2 `npm run screenshots`: check that there is no horizontal overflow on `/admin/invitations` or `/staff/dashboard` at any width, that the admin bar is on one row at desktop width, and that the staff dashboard capture looks unchanged.
- [ ] 3.3 Manually on `/admin/invitations`:
  - Purpose narrows every column and updates the counts.
  - Status "Approved" loads only the Approved column.
  - Source narrows the board.
  - "Clear filters" appears only while a filter is set, resets all four filters, and keeps the search text.
- [x] 3.4 Add a CHANGELOG entry: the admin Invitations filters are now inline and match the staff dashboard, a Purpose filter was added, and the Filters toggle was removed.
