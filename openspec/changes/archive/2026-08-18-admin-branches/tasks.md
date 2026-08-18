## 1. Domain schema

- [x] 1.1 Add `src/domain/entities/branch-schema.ts` with `BranchSchema` (id, name, locationCity, branchCode, contactPerson, status: `'active' | 'inactive'`) and its `z.infer` type

## 2. API endpoints

- [x] 2.1 Add `LIST_BRANCHES` (`GET /branches`, `hasToken: true`), `CREATE_BRANCH` (`POST /branches`, `hasToken: true`), `UPDATE_BRANCH` (`PUT /branches`, `hasToken: true`, id passed via query param), `DELETE_BRANCH` (`DELETE /branches`, `hasToken: true`, id passed via query param) to `src/data/api/api-endpoints.ts`

## 3. Repository port, adapter, use cases

- [x] 3.1 Add `src/data/repositories/branch-repository.ts` with `BranchRepository` interface: `list(): Promise<Branch[]>`, `create(input: Omit<Branch, 'id'>): Promise<Branch>`, `update(id: string, input: Omit<Branch, 'id'>): Promise<Branch>`, `remove(id: string): Promise<void>`
- [x] 3.2 Add `src/infrastructure/branch-repository.ts` implementing `BranchRepository` via `ApiClient.makeRequest` against the new endpoints and schema (list returns `z.array(BranchSchema)`)
- [x] 3.3 Add `src/data/use-cases/list-branches.ts` (`ListBranchesUseCase`)
- [x] 3.4 Add `src/data/use-cases/create-branch.ts` (`CreateBranchUseCase`)
- [x] 3.5 Add `src/data/use-cases/update-branch.ts` (`UpdateBranchUseCase`)
- [x] 3.6 Add `src/data/use-cases/delete-branch.ts` (`DeleteBranchUseCase`)

## 4. Composition root

- [x] 4.1 Wire `resolveBranchRepository`, `resolveListBranchesUseCase`, `resolveCreateBranchUseCase`, `resolveUpdateBranchUseCase`, `resolveDeleteBranchUseCase` in `src/composition-root.ts` and expose the four use cases on `AppDependencies`

## 5. Shared UI: Modal and top bar promotion

- [x] 5.1 Add `src/presentation/components/ui/Modal.tsx` (`{ isOpen, onClose, title, children }`)
- [x] 5.2 Add `src/presentation/components/ui/ConfirmDialog.tsx` built on `Modal` (`{ isOpen, title, message, confirmLabel, onConfirm, onCancel }`)
- [x] 5.3 Add `src/presentation/components/AdminTopBar.tsx` (title fixed "Organization Admin", `description` and `currentUser` props), moving the markup out of `admin-organisation-configs/Components/TopBar.tsx`
- [x] 5.4 Update `admin-organisation-configs.tsx` to render `AdminTopBar` with its existing description text, and delete the now-unused `admin-organisation-configs/Components/TopBar.tsx`

## 6. Page: hook and data flow

- [x] 6.1 Add `src/presentation/pages/admin-branches/hooks/use-admin-branches.ts`: checks `sessionStorage` token on mount (redirect to `/staff/login` if missing), loads current staff user + branch list, exposes loading/error/retry, `openAddForm`, `openEditForm(branch)`, `closeForm`, `saveBranch` (creates or updates depending on which form is open, merges the result into local state, toasts on success/failure), `requestDelete(branch)`, `confirmDelete`, `cancelDelete` (removes the branch from local state on success, toasts on success/failure)
- [x] 6.2 In the hook, keep list state, the open add/edit form's draft values, and the pending-delete branch as separate pieces of state so form/dialog visibility and list content update independently

## 7. Page: components and layout

- [x] 7.1 Add `src/presentation/pages/admin-branches/Components/BranchesTable.tsx`: table header (Branch Name, Location/City, Branch Code, Contact Person, Status, Actions) and one row per branch with an Active/Inactive badge and Edit/Delete icon buttons (reusing `PencilIcon`/`TrashIcon`)
- [x] 7.2 Add `src/presentation/pages/admin-branches/Components/BranchFormModal.tsx`: `Modal`-based form (name, location/city, branch code, contact person as `TextField`s, status as `ToggleSwitch`) used for both Add and Edit, with required-field validation on submit
- [x] 7.3 Add `src/presentation/pages/admin-branches/admin-branches.tsx`: renders `AdminSidebar` (`activeItem="branches"`), `AdminTopBar`, content header ("Branches Register" title, inert "Filters", "Add Branch"), `LoadingState`/inline-error-with-retry/`EmptyState`/`BranchesTable` depending on state, `BranchFormModal`, and a `ConfirmDialog` for delete

## 8. Routing

- [x] 8.1 Add the `/admin/branches` route to `src/App.tsx` rendering the new page

## 9. Verification

- [x] 9.1 Run the dev server and visually compare `/admin/branches` against the Figma design (node `203:148`) for layout, spacing, and color fidelity
- [x] 9.2 Manually verify: auth redirect, list load/error/retry, empty state with zero branches, add branch (validation + success + failure), edit branch (pre-fill + success + failure), delete branch (confirm dialog, cancel, success, failure), inert Filters
- [x] 9.3 Confirm `admin-organisation-configs` still renders correctly after the `AdminTopBar` extraction
- [x] 9.4 Run lint/type-check and any existing test suite
