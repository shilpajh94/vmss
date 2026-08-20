## Why

Admins can register departments, branches, and buildings, but there is no way to manage the internal staff who actually sponsor and host visitors. The Figma design (node `203:1595`) defines a Host Employees Directory; building it activates the `'host-employees'` entry that `AdminSidebar` already reserves but never wires to a route, and gives admins a place to manage who can be selected as a host elsewhere in the product.

## What Changes

- Add a new `/admin/host-employees` page rendering the Admin shell (`AdminSidebar` with `activeItem="host-employees"`, `AdminTopBar`) with a table of host employees (name, department, branch, email, role/access, status) and per-row Edit/Delete
- Add a dedicated `/admin/host-employees/new` and `/admin/host-employees/:id/edit` create/edit form (name, department select, email, role/access select, status toggle), following the same dedicated-page pattern established by `admin-departments`/`admin-buildings`/`admin-floors` — branch is derived from the selected department, not entered separately, since `Department` is already branch-scoped
- Wire `AdminSidebar`'s existing `'host-employees'` key to navigate to `/admin/host-employees`
- Per explicit user direction, "Import Hosts" (the design's only header action) stays visually present but inert for this pass, matching the project's existing pattern for not-yet-scoped affordances (e.g. `admin-branches`' "Filters"); the "Filters" control is likewise inert
- Add a new `HostEmployee` domain schema, API endpoints, repository port/adapter, and use cases for list/create/update/delete

## Capabilities

### New Capabilities
- `admin-host-employees`: the Super Admin's Host Employees Directory at `/admin/host-employees` — list, add, edit, and delete host employees, each tied to a department (and, through it, a branch), an email address, a role/access level, and a status.

### Modified Capabilities
(none — `AdminSidebar`'s host-employees-key wiring is an internal implementation detail of the new page, not a change to any other capability's documented requirements)

## Impact

- New pages: `src/presentation/pages/admin-host-employees/`
- New routes: `/admin/host-employees`, `/admin/host-employees/new`, `/admin/host-employees/:id/edit` in `src/App.tsx`
- Modified: `src/presentation/components/AdminSidebar.tsx` (wire the `'host-employees'` nav item)
- New domain schema, API endpoints, repository port/adapter, and use cases for host employees
