## 1. Relabel the sidebar and page shell

- [x] 1.1 In `src/presentation/components/AdminSidebar.tsx`, change the `host-employees` nav item's `label` from `'Host Employees'` to `'Employees'` (leave the `'host-employees'` key/route untouched).
- [x] 1.2 In `src/presentation/pages/admin-host-employees/admin-host-employees.tsx`, change the page title from "Host Employees Directory" to "Employees Directory".

## 2. Relabel buttons, empty state, and toasts on the list page

- [x] 2.1 In `src/presentation/pages/admin-host-employees/admin-host-employees.tsx`, change "Add Host Employee" (button label and `EmptyState` action label) to "Add Employee", and "No host employees yet." to "No employees yet." (Also relabeled the "No host employees match these filters." empty state added by the concurrently-implemented `filter-host-employees` change, for consistency.)
- [x] 2.2 In `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts`, change the load-failure error/toast text from "Something went wrong loading the host employees. Please try again." to "Something went wrong loading the employees. Please try again."

## 3. Relabel the Add/Edit form page

- [x] 3.1 In `src/presentation/pages/admin-host-employees/admin-host-employee-form.tsx`, change the page title from "Manage Host Employee Access" / "Add Host Employee" to "Manage Employee Access" / "Add Employee", and the submit button from "Save Host Employee" to "Save Employee".
- [x] 3.2 In `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employee-form.ts`, change "That host employee could not be found." to "That employee could not be found.", "Host employee created." to "Employee created.", and "Something went wrong creating the host employee. Please try again." to "Something went wrong creating the employee. Please try again." (No separate update-failure message exists — edit mode only manages role assignment, not a full record update.)

## 4. Relabel cross-referencing prose

- [x] 4.1 No code change needed for `admin-organisation-configs` or `admin-reception-desks` beyond what's already covered by task 1.1 (the sidebar label) — their spec deltas only relabel prose describing that same sidebar item and the Reception Desk form's Assigned Receptionist source, which already draws its options from the same employee data task 1 doesn't change functionally.

## 5. Update the capability's Purpose sentence (manual, outside the delta mechanism)

- [ ] 5.1 After this change is synced to main specs, directly edit `openspec/specs/admin-host-employees/spec.md`'s `## Purpose` line to say "Employees Directory" / "Employees" instead of "Host Employees Directory" / "Host Employees" — archive/sync deliberately leaves an existing capability's Purpose untouched, so this one sentence needs a manual follow-up edit.

## 6. Verify

- [ ] 6.1 Load `/admin/host-employees`, confirm the sidebar reads "Employees", the page title reads "Employees Directory", and the "Add Employee" button/empty-state action are relabeled.
- [ ] 6.2 Open the Add/Edit page and confirm the title and "Save Employee" button are relabeled.
- [ ] 6.3 Trigger a load failure (e.g. offline) and confirm the toast reads "...loading the employees...".
- [ ] 6.4 Confirm the route `/admin/host-employees` and the sidebar's internal `activeItem` still work exactly as before (no navigation regression) — only the visible label changed.
