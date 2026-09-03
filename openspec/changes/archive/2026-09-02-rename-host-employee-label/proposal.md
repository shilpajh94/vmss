## Why

The admin wants "Host Employee(s)" relabeled to "Employee(s)" throughout the admin UI. Scoped to visible text only: the underlying `HostEmployee` type, use cases, repository, file names, and the `/admin/host-employees` route are shared across ~20+ files in other features (departments, branches, reception-desks, dashboard, invitations, staff audit trail) — renaming those is a much larger, separate-risk change and is explicitly out of scope here.

## What Changes

- Relabel every user-visible occurrence of "Host Employee(s)" to "Employee(s)" on the Host Employees Directory and its Add/Edit page: sidebar nav label, page titles, buttons ("Add Host Employee" → "Add Employee", "Save Host Employee" → "Save Employee"), the empty-state message and its action label, toasts/error messages, and the not-found message.
- Also relabel the two cross-referencing mentions in other specs' prose (`admin-organisation-configs` sidebar nav list, `admin-reception-desks` prose referencing "host employees" as the receptionist-assignment source) for consistency, since they describe the same sidebar item and data by name.
- **Out of scope (unchanged)**: the `HostEmployee` domain type, `HostEmployeeRepository`, `*HostEmployeeUseCase` classes, file/directory names under `src/presentation/pages/admin-host-employees/` and `src/data`/`src/infrastructure`, the `/admin/host-employees` route path, and the OpenSpec capability directory name `admin-host-employees` itself. These stay as-is; a future change can tackle them separately if wanted.
- Also out of scope: "Import Hosts" button label — not a literal "Host Employee" match, and changing it isn't part of the requested rename.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-host-employees`: every requirement's prose and scenario text referencing "Host Employee(s)" is relabeled to "Employee(s)"; the capability's own Purpose sentence is updated to match (edited directly in the main spec per delta-spec convention, not via a delta, since Purpose changes for an existing capability aren't carried through deltas).
- `admin-organisation-configs`: the sidebar navigation list requirement's prose lists "Employees" instead of "Host Employees".
- `admin-reception-desks`: prose referencing "host employees" as the source for receptionist assignment is relabeled to "employees".

## Impact

- `src/presentation/components/AdminSidebar.tsx` — nav item label "Host Employees" → "Employees" (the `'host-employees'` key/route stays unchanged, per the out-of-scope note above).
- `src/presentation/pages/admin-host-employees/admin-host-employees.tsx` — page title, "Add Host Employee" button, empty-state message and action label.
- `src/presentation/pages/admin-host-employees/admin-host-employee-form.tsx` — form page title ("Add Host Employee" / "Manage Host Employee Access"), "Save Host Employee" button.
- `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts` — load-failure error/toast text.
- `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employee-form.ts` — not-found message, create-success/create-failure toast text.
- No change to routes, file names, the `HostEmployee` domain type, or any use-case/repository/component identifier.
