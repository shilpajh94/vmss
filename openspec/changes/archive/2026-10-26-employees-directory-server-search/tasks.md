## 1. Data layer

- [x] 1.1 Add `search?: string` to `ListHostEmployeesPageParams` in `src/data/repositories/host-employee-repository.ts`
- [x] 1.2 Pass `search` in `queryParams` in `listPage` in `src/infrastructure/host-employee-repository.ts`

## 2. Hook

- [x] 2.1 In `use-admin-host-employees.ts`, add `search` state and `useDebouncedValue(search, 300)`; send `debouncedSearch.trim() || undefined` to `listHostEmployeesPageUseCase.execute` and add it to the `loadHostEmployees` dependencies
- [x] 2.2 Reset to page 1 when the debounced search changes (not on initial mount)
- [x] 2.3 Treat an active debounced search as "filtering" for the empty-state message only; leave `clearFilters` not touching the search text
- [x] 2.4 Return `search` and `setSearch` from the hook

## 3. UI

- [x] 3.1 Add a search input (glyph icon, `maxLength={255}`, `aria-label`, placeholder like "Search name, email, code...") to the header row of `admin-host-employees.tsx`, wired to `search`/`setSearch`
- [x] 3.2 Update the empty-state copy to "No employees match your search or filters." when searching/filtering

## 4. Verification

- [ ] 4.1 Add/extend unit tests: blank search omits the param, trimmed text is sent, page resets on search change, empty-state message
  - Not done: the repo has no unit-test runner (no vitest/jest); adding one is out of scope for this change.
- [x] 4.2 Run `npm run lint` and `npm run build`
- [ ] 4.3 Manually check in the dev server: search "srch-00" style code match, search + filters combine, pagination totals, no request per keystroke
