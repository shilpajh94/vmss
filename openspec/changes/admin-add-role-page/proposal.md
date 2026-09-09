## Why

The admin Roles & Permissions screen (`/admin/roles`) can only list roles and edit an existing role's permissions — there is no way for a Super Admin to create a new custom role from the UI. Admins currently have no self-serve path to add a role, forcing manual backend intervention whenever a new role is needed.

## What Changes

- Add an "Add Role" action on the Roles list (`/admin/roles`) that opens a new create-role page.
- Add a new page at `/admin/roles/new` where an admin enters a role name, an optional description, and selects granted permissions from the full permission catalog (same checklist UI as the existing permission-edit page).
- On submit, create the role via a new `POST /auth/roles` endpoint; on success, navigate back to the Roles list and show a success notification; on failure, show an error notification and keep the admin on the form.
- On cancel, discard the draft and return to the Roles list without creating anything.
- Wire the new endpoint through `ApiClient`, a new `createRole` port method, a `CreateRoleUseCase`, and the composition root, following this repo's existing data-api-layer pattern (same one used for `listRoles`/`updateRolePermissions`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-roles`: adds the ability to create a new role from an "Add Role" page, in addition to the existing list and permission-edit behavior.

## Impact

- `src/data/api/api-endpoints.ts`: new `CREATE_ROLE` entry (`POST /auth/roles`, `hasToken: true`).
- `src/domain/entities/role-out-schema.ts`: new create-input type (name, optional description, permission codes).
- `src/data/repositories/host-employee-repository.ts`: new `createRole` method on the existing roles/host-employee port.
- `src/infrastructure/host-employee-repository.ts`: implement `createRole` using `ApiClient.makeRequest`.
- `src/data/use-cases/`: new `create-role.ts` use case.
- `src/composition-root.ts`: resolve and expose `createRoleUseCase` on `AppDependencies`.
- `src/presentation/pages/admin-roles/`: new create-role page + hook; "Add Role" button added to the existing Roles list page.
- `src/App.tsx`: new route `/admin/roles/new`.
