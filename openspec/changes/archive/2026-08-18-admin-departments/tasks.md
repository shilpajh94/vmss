## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/department-schema.ts` with `DepartmentSchema` (id, name, branchId, branchName, headOfDepartment optional, description optional, status: `'active' | 'inactive'`, employeeCount) and its `z.infer` type, plus a `DepartmentInputSchema`/type for create/edit payloads (name, branchId, headOfDepartment optional, description optional, status) that excludes `id`, `branchName`, and `employeeCount`

## 2. API endpoints

- [x] 2.1 Add `LIST_DEPARTMENTS` (`GET /departments`, `hasToken: true`), `CREATE_DEPARTMENT` (`POST /departments`, `hasToken: true`), `UPDATE_DEPARTMENT` (`PUT /departments`, `hasToken: true`, id via query param), `DELETE_DEPARTMENT` (`DELETE /departments`, `hasToken: true`, id via query param) to `src/data/api/api-endpoints.ts`

## 3. Repository port, adapter, use cases

- [x] 3.1 Add `src/data/repositories/department-repository.ts` with `DepartmentRepository` interface: `list(): Promise<Department[]>`, `create(input: DepartmentInput): Promise<Department>`, `update(id: string, input: DepartmentInput): Promise<Department>`, `remove(id: string): Promise<void>`
- [x] 3.2 Add `src/infrastructure/department-repository.ts` implementing `DepartmentRepository` via `ApiClient.makeRequest` against the new endpoints and schema (list returns `z.array(DepartmentSchema)`)
- [x] 3.3 Add `src/data/use-cases/list-departments.ts` (`ListDepartmentsUseCase`)
- [x] 3.4 Add `src/data/use-cases/create-department.ts` (`CreateDepartmentUseCase`)
- [x] 3.5 Add `src/data/use-cases/update-department.ts` (`UpdateDepartmentUseCase`)
- [x] 3.6 Add `src/data/use-cases/delete-department.ts` (`DeleteDepartmentUseCase`)

## 4. Composition root

- [x] 4.1 Wire `resolveDepartmentRepository`, `resolveListDepartmentsUseCase`, `resolveCreateDepartmentUseCase`, `resolveUpdateDepartmentUseCase`, `resolveDeleteDepartmentUseCase` in `src/composition-root.ts` and expose the four use cases on `AppDependencies`

## 5. Sidebar wiring

- [x] 5.1 Add a `departments` case to `AdminSidebar.tsx`'s `handleActivate` that navigates to `/admin/departments`

## 6. Departments list page

- [x] 6.1 Add `src/presentation/pages/admin-departments/hooks/use-admin-departments.ts`: auth-token gate, loads current staff user + department list, exposes loading/error/retry, `requestDelete`, `cancelDelete`, `confirmDelete` (mirrors `use-admin-branches.ts`'s list/delete half, minus any form state)
- [x] 6.2 Add `src/presentation/pages/admin-departments/Components/DepartmentsTable.tsx`: table header (Department Name, Branch, Head of Department, Employee Count, Status, Actions) and one row per department with an Active/Inactive badge and Edit/Delete icon buttons
- [x] 6.3 Add `src/presentation/pages/admin-departments/admin-departments.tsx`: renders `AdminSidebar` (`activeItem="departments"`), `AdminTopBar` (description mode), content header ("Departments Register" title, inert "Filters", "Add Department" navigating to `/admin/departments/new`), `LoadingState`/inline-error-with-retry/`EmptyState`/`DepartmentsTable` depending on state, and a `ConfirmDialog` for delete

## 7. Add/Edit Department page

- [x] 7.1 Add `src/presentation/pages/admin-departments/hooks/use-admin-department-form.ts`: auth-token gate; reads an optional `:id` route param — when present, loads that department via `listDepartmentsUseCase` (or a dedicated fetch) and pre-fills the form in edit mode, otherwise starts empty in add mode; loads the branch list via `listBranchesUseCase` for the Branch dropdown; exposes `updateField`, `submit` (validates name/branch required, calls create or update depending on mode, on success navigates to `/admin/departments` and toasts success, on failure toasts error and keeps entered values), and `cancel` (navigates to `/admin/departments`)
- [x] 7.2 Add `src/presentation/pages/admin-departments/admin-department-form.tsx`: renders `AdminSidebar` (`activeItem="departments"`), `AdminTopBar` (description mode), a back button + "Add Department"/"Edit Department" header, a form card (Department Name `TextField`, Branch `SelectField` populated from the loaded branch list, Head of Department `TextField`, Description `TextareaField`, Department Status `ToggleSwitch`), and Cancel/Save Department (or Save Changes) footer actions

## 8. Routing

- [x] 8.1 Add `/admin/departments`, `/admin/departments/new`, and `/admin/departments/:id/edit` routes to `src/App.tsx`

## 9. Verification

- [x] 9.1 Run the dev server and visually compare `/admin/departments` and `/admin/departments/new` against the Figma designs (nodes `203:307` and `217:5`) for layout, spacing, and color fidelity
- [x] 9.2 Manually verify: Departments nav item navigates, list load/error/retry, empty state, Add Department navigation + validation + success + failure, Branch dropdown populated from real branch data, Edit pre-fills and updates, Delete confirm/cancel/success/failure, inert Filters
- [x] 9.3 Run lint/type-check and any existing test suite
