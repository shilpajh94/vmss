## 1. Endpoint & domain schema

- [x] 1.1 Add `CREATE_ROLE` to `API_ENDPOINTS` in `src/data/api/api-endpoints.ts` (`endpoint: "/auth/roles"`, `method: "POST"`, `hasToken: true`)
- [x] 1.2 Add `RoleCreateInput` (`name: string`, `description?: string`, `permissionCodes: string[]`) to `src/domain/entities/role-out-schema.ts`

## 2. Port & adapter

- [x] 2.1 Add `createRole(input: RoleCreateInput): Promise<RoleOut>` to `HostEmployeeRepository` in `src/data/repositories/host-employee-repository.ts`
- [x] 2.2 Implement `createRole` in `src/infrastructure/host-employee-repository.ts` using `this.apiClient.makeRequest` with `API_ENDPOINTS.CREATE_ROLE` and `RoleResponseSchema`

## 3. Use case

- [x] 3.1 Add `src/data/use-cases/create-role.ts` (`CreateRoleUseCase`, constructor-injected `HostEmployeeRepository`, `execute(input: RoleCreateInput): Promise<RoleOut>` delegating to the port)

## 4. Composition root

- [x] 4.1 Add `createRoleUseCase` to the `AppDependencies` interface and its lazy resolver in `src/composition-root.ts`, following the existing `resolveUpdateRolePermissionsUseCase` pattern

## 5. Create-role page

- [x] 5.1 Add `src/presentation/pages/admin-roles/hooks/use-admin-role-create-form.ts`: guards the staff-auth token (redirect to `/admin/login`), loads current user + permission catalog via `getCurrentStaffUserUseCase` / `listPermissionsUseCase`, holds `name`, `description`, `selectedCodes` state, validates non-blank `name` on submit, calls `createRoleUseCase.execute(...)`, and on success navigates to `/admin/roles` with a success toast; on failure shows an error toast and keeps entered values; `cancel()` navigates to `/admin/roles` without submitting
- [x] 5.2 Add `src/presentation/pages/admin-roles/admin-role-create-form.tsx` (`AdminRoleCreateFormPage`): renders `AdminSidebar`/`AdminTopBar` (breadcrumb `Roles & Permissions > Add Role`), name input, description input, the permission checklist (reusing the layout from `admin-role-permissions-form.tsx`), and Cancel / "Create Role" actions wired to the hook
- [x] 5.3 Add the "Add Role" button to `src/presentation/pages/admin-roles/admin-roles.tsx` header, navigating to `/admin/roles/new`

## 6. Routing

- [x] 6.1 Add `<Route path="/admin/roles/new" element={<AdminRoleCreateFormPage />} />` in `src/App.tsx`, registered before or after `/admin/roles/:id/edit` such that `/admin/roles/new` is not swallowed by the `:id` param route

## 7. Verification

- [ ] 7.1 Run the app and manually verify: Add Role → fill name + permissions → Create Role → lands back on Roles list with the new role shown as Custom
- [ ] 7.2 Verify blank-name validation blocks submit without a network call
- [ ] 7.3 Verify Cancel returns to the Roles list without creating a role
- [ ] 7.4 Verify a simulated backend failure shows an error toast and preserves entered form values
- [ ] 7.5 Verify an unauthenticated browser navigating to `/admin/roles/new` redirects to `/admin/login`
