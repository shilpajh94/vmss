## Why

The Admin section needs its "Departments" screen, per Figma: a list (node `203:307`, "Departments Register") and a dedicated Add Department page (node `217:5`). Unlike Branches, both designs exist, so this ships as full CRUD from the start, matching the precedent set by `admin-branches`.

## What Changes

- Add the **Departments** page (`/admin/departments`) rendering the Admin shell (`AdminSidebar` with "Departments" active, `AdminTopBar` in description mode) and a "Departments Register" table matching the Figma design: Department Name, Branch, Head of Department, Employee Count, Status (Active/Inactive badge), and row actions (Edit, Delete).
- Add the **Add Department** page (`/admin/departments/new`) matching Figma node `217:5`: a back button + "Add Department" header, a form card (Department Name*, Branch* — a real dropdown populated from the existing Branches list, Head of Department, Description, Department Status toggle), and Cancel/Save Department footer actions.
- **Edit Department** reuses the same page component at `/admin/departments/:id/edit` (pre-filled, titled "Edit Department"/"Save Changes"), since no separate edit design exists and the Add page's form is generic enough to serve both — this mirrors how `admin-branches` reused one form for add and edit, just as a page instead of a modal here.
- **Delete Department** opens the existing shared `ConfirmDialog` before removing a department, mirroring `admin-branches`'s delete flow.
- The Branch dropdown is the first real cross-capability integration in the Admin section: it calls the existing `listBranchesUseCase` (from `admin-branches`) to populate real branch options, rather than a hardcoded list.
- "Head of Department" stays free text (no dropdown backed by real data), for the same reason `admin-branches`'s "Contact Person" stayed free text: no employee directory exists yet (Host Employees isn't built). Employee Count is a read-only, backend-supplied value shown in the table; it is never submitted by the admin.
- "Filters" is presented per the design but stays inert, matching the established pattern.
- Wires the `AdminSidebar`'s existing "Departments" nav item (its key and label already exist from `admin-branches`, but it wasn't yet clickable) to navigate to `/admin/departments`.

## Capabilities

### New Capabilities
- `admin-departments`: the Departments Register page and the Add/Edit Department page — listing departments, and adding, editing, and deleting a department.

## Impact

- **New routes**: `/admin/departments`, `/admin/departments/new`, `/admin/departments/:id/edit` in `src/App.tsx`.
- **Changed presentation code**: `AdminSidebar.tsx`'s `handleActivate` gains a `departments` case that navigates to `/admin/departments`.
- **New presentation code**: `src/presentation/pages/admin-departments/` (list page, form page, hook(s), components).
- **New domain schema**: `src/domain/entities/department-schema.ts`.
- **New data layer**: `src/data/repositories/department-repository.ts` (port), `src/data/use-cases/list-departments.ts`, `src/data/use-cases/create-department.ts`, `src/data/use-cases/update-department.ts`, `src/data/use-cases/delete-department.ts`.
- **New infrastructure**: `src/infrastructure/department-repository.ts` (adapter), new entries in `src/data/api/api-endpoints.ts` (`LIST_DEPARTMENTS`, `CREATE_DEPARTMENT`, `UPDATE_DEPARTMENT`, `DELETE_DEPARTMENT`).
- **Composition root**: `src/composition-root.ts` gains `departmentRepository`, `listDepartmentsUseCase`, `createDepartmentUseCase`, `updateDepartmentUseCase`, `deleteDepartmentUseCase` on `AppDependencies`.
- **No change** to `admin-branches` — its `listBranchesUseCase` is consumed as-is by the new Branch dropdown.
- **No backend changes are made by this change** — it assumes the four new endpoints exist; exact request/response shapes are defined in the new domain schema.
