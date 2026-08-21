## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/host-employee-schema.ts` with `HostEmployeeSchema` (id, name, departmentId, departmentName, branchName, email, roleAccess: `'host' | 'security-admin' | 'system-admin'`, status: `'active' | 'inactive'`), its `z.infer` type, and `HostEmployeeInputSchema` (`.pick`: name, departmentId, email, roleAccess, status) with its `z.infer` type

## 2. API endpoints

- [x] 2.1 Add `LIST_HOST_EMPLOYEES` (`GET /host-employees`, `hasToken: true`), `CREATE_HOST_EMPLOYEE` (`POST /host-employees`, `hasToken: true`), `UPDATE_HOST_EMPLOYEE` (`PUT /host-employees`, `hasToken: true`, id via query param), `DELETE_HOST_EMPLOYEE` (`DELETE /host-employees`, `hasToken: true`, id via query param) to `src/data/api/api-endpoints.ts`

## 3. Repository port, adapter, use cases

- [x] 3.1 Add `src/data/repositories/host-employee-repository.ts` with `HostEmployeeRepository` interface: `list(): Promise<HostEmployee[]>`, `create(input: HostEmployeeInput): Promise<HostEmployee>`, `update(id: string, input: HostEmployeeInput): Promise<HostEmployee>`, `remove(id: string): Promise<void>`
- [x] 3.2 Add `src/infrastructure/host-employee-repository.ts` implementing `HostEmployeeRepository` via `ApiClient.makeRequest` against the new endpoints and schema
- [x] 3.3 Add `src/data/use-cases/list-host-employees.ts` (`ListHostEmployeesUseCase`)
- [x] 3.4 Add `src/data/use-cases/create-host-employee.ts` (`CreateHostEmployeeUseCase`)
- [x] 3.5 Add `src/data/use-cases/update-host-employee.ts` (`UpdateHostEmployeeUseCase`)
- [x] 3.6 Add `src/data/use-cases/delete-host-employee.ts` (`DeleteHostEmployeeUseCase`)

## 4. Composition root

- [x] 4.1 Wire `resolveHostEmployeeRepository`, `resolveListHostEmployeesUseCase`, `resolveCreateHostEmployeeUseCase`, `resolveUpdateHostEmployeeUseCase`, `resolveDeleteHostEmployeeUseCase` in `src/composition-root.ts` and expose the four use cases on `AppDependencies`

## 5. Sidebar wiring

- [x] 5.1 In `src/presentation/components/AdminSidebar.tsx`, add a `'host-employees'` case to `handleActivate` that navigates to `/admin/host-employees`

## 6. Page: list — hook and data flow

- [x] 6.1 Add `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts`: checks `sessionStorage` token on mount (redirect to `/staff/login` if missing), loads current staff user + host employee list, exposes loading/error/retry, `requestDelete(hostEmployee)`, `confirmDelete`, `cancelDelete` (removes the host employee from local state on success, toasts on success/failure)

## 7. Page: list — components and layout

- [x] 7.1 Add `src/presentation/pages/admin-host-employees/Components/HostEmployeesTable.tsx`: table header (Employee Name, Department, Branch, Email Address, Role/Access, Status, Actions) and one row per host employee, with a role/access badge (color mapped per role) and an Active/Inactive status badge, Edit navigates to `/admin/host-employees/:id/edit`, Delete triggers the confirm flow
- [x] 7.2 Add `src/presentation/pages/admin-host-employees/admin-host-employees.tsx`: renders `AdminSidebar` (`activeItem="host-employees"`), `AdminTopBar`, content header ("Host Employees Directory" title, inert "Filters", inert "Import Hosts", "Add Host Employee"), `LoadingState`/inline-error-with-retry/`EmptyState`/`HostEmployeesTable` depending on state, and a `ConfirmDialog` for delete

## 8. Page: create/edit form

- [x] 8.1 Add `src/presentation/pages/admin-host-employees/hooks/use-admin-host-employee-form.ts`: checks `sessionStorage` token, detects edit mode from a route `:id` param, loads current staff user + department list (+ the host employee list to find the record being edited, in edit mode), exposes `values`/`errors`/`isSaving`/`updateField`/`submit`/`cancel`, validates name/departmentId/email/roleAccess as non-empty on submit, calls create or update depending on mode, navigates back to `/admin/host-employees` on success with a success toast, and on failure toasts an error while keeping the admin on the form with entered values
- [x] 8.2 Add `src/presentation/pages/admin-host-employees/admin-host-employee-form.tsx`: renders `AdminSidebar`/`AdminTopBar`, a back button, "Add Host Employee" / "Edit Host Employee" heading, `TextField` for name, `SelectField` for department (options from the loaded department list) with the derived branch name shown read-only beneath it, `TextField` for email, `SelectField` for role/access (Host / Security Admin / System Admin), a `ToggleSwitch` for status, and Cancel/Save actions

## 9. Routing

- [x] 9.1 Add `/admin/host-employees`, `/admin/host-employees/new`, and `/admin/host-employees/:id/edit` routes to `src/App.tsx` rendering the new pages

## 10. Verification

- [x] 10.1 Run the dev server and visually compare `/admin/host-employees` against the Figma design (node `203:1595`) for layout, spacing, and color fidelity
- [x] 10.2 Manually verify: auth redirect, list load/error/retry, empty state with zero host employees, add host employee (validation + success + failure, department selection deriving the shown branch), edit host employee (pre-fill + success + failure), delete host employee (confirm dialog, cancel, success, failure), inert Filters and Import Hosts, sidebar "Host Employees" navigation from other admin pages
- [x] 10.3 Run lint/type-check and any existing test suite
