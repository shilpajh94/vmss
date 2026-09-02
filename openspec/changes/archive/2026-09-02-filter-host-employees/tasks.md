## 1. Add filter state and derived list to the hook

- [x] 1.1 In `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts`, add filter state: `departmentFilter`, `roleFilter`, `statusFilter` (each `string`, default `''` meaning "All"), and a boolean `isFilterPanelOpen`.
- [x] 1.2 Add a `useMemo` deriving `roleOptions`: the deduplicated, sorted list of `roleName` values across every employee's `branchRoles`.
- [x] 1.3 Add a `useMemo` deriving `filteredHostEmployees` from `hostEmployees` by applying `departmentFilter` (match `departmentId`), `roleFilter` (match any `branchRoles[].roleName`), and `statusFilter` (`'active'`/`'inactive'` matched against `isActive`) — a filter counts only when its value is non-empty.
- [x] 1.4 Add `setDepartmentFilter`, `setRoleFilter`, `setStatusFilter`, `clearFilters` (resets all three to `''`), and `toggleFilterPanel` callbacks, and return all of the above (plus `filteredHostEmployees` in place of the raw list) from the hook.

## 2. Build the filter panel UI

- [x] 2.1 In `src/presentation/pages/admin-host-employees/admin-host-employees.tsx`, wire the existing "Filters" button's `onClick` to `toggleFilterPanel`.
- [x] 2.2 Add a filter panel (new component or inline JSX) shown when `isFilterPanelOpen`, with three `SelectField`s — Department (options from `departments`, plus "All"), Role (options from `roleOptions`, plus "All"), Status (Active/Inactive, plus "All") — and a "Clear filters" action calling `clearFilters`. (Note: "All" is provided by `SelectField`'s own built-in placeholder option rather than a duplicate manual entry — see task note below.)
- [x] 2.3 Pass `filteredHostEmployees` (not the raw `hostEmployees`) into `<HostEmployeesTable>`.

## 3. Distinguish the two empty states

- [x] 3.1 In `admin-host-employees.tsx`, when `filteredHostEmployees` is empty: show "No host employees match these filters." if any filter is active, or the existing "No host employees yet." empty state (with its "Add Host Employee" action) if the unfiltered list is also empty and no filter is active.

## 4. Verify

- [ ] 4.1 Load `/admin/host-employees`, activate "Filters", confirm the panel shows Department/Role/Status selects each defaulting to "All".
- [ ] 4.2 Select a Department and confirm the table narrows to only employees in that department; repeat for Role and Status; select combinations and confirm they combine (AND semantics).
- [ ] 4.3 Pick a filter combination matching zero employees and confirm the "no host employees match these filters" message shows (not the "Add Host Employee" empty state).
- [ ] 4.4 Activate "Clear filters" and confirm the full list returns and all selects reset to "All".
