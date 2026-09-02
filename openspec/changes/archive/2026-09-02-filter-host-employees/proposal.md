## Why

The "Filters" control on the Host Employees Directory is currently a non-functional placeholder (per the existing spec, matching the same inert pattern used by Buildings, Branches, and other admin list pages). The admin wants it to actually filter the directory rather than remain decorative — with departments and roles growing, finding a specific employee by scrolling an unfiltered table doesn't scale.

## What Changes

- "Filters" becomes a real, working control on the Host Employees Directory: activating it opens a filter panel with three fields — **Department**, **Role**, and **Status** (Active/Inactive) — each defaulting to "All".
- Filtering is applied client-side against the already-loaded host employee list (no new backend endpoint or query params needed — the full list and department names are already fetched on page load).
- Changing any filter updates the visible table immediately (no separate "Apply" step); a "Clear filters" action resets all three back to "All".
- When filters are active and no employees match, the table shows a distinct "No host employees match these filters." message instead of the existing "no host employees at all" empty state.
- "Import Hosts" is unaffected by this change and remains a non-functional placeholder.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-host-employees`: "Filters ... presented but not yet functional" no longer applies to Filters (Import Hosts keeps that behavior); a new requirement describes the working Department/Role/Status filter panel and its interaction with the list and empty state.

## Impact

- `src/presentation/pages/admin-host-employees/admin-host-employees.tsx` — wire the "Filters" button to toggle a new filter panel component.
- `src/presentation/pages/admin-host-employees/Components/HostEmployeesTable.tsx` (or a new sibling component for the filter panel) — render the three filter controls (reusing the existing `SelectField` component) and the "Clear filters" action.
- `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts` — add filter state (department, role, status) and derive the filtered list via `useMemo` over the already-loaded `hostEmployees` and `departments`; derive the distinct role options from `hostEmployees[].branchRoles[].roleName`.
- No changes to `src/domain/entities/host-employee-schema.ts`, `src/data/use-cases/list-host-employees.ts`, `src/data/repositories/host-employee-repository.ts`, `src/infrastructure/host-employee-repository.ts`, or `API_ENDPOINTS.LIST_HOST_EMPLOYEES` — filtering happens entirely over data already in memory.
