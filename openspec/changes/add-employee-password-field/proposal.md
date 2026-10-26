## Why

The Add Employee page has no way to give a new employee a password, so an admin cannot create an employee who can sign in with email + password. Today a newly added employee has no password set at all.

## What Changes

- Add an optional **Password** field (masked, with a show/hide toggle) to the Add Employee create form at `/admin/host-employees/new`.
- Validate a non-empty password client-side (minimum length) before submit; leaving it blank keeps today's behaviour (no password set).
- After the employee sync succeeds, set the password via `POST /auth/users` (email, password, fullName). The sync endpoint has no password field.
- The password is never echoed back, logged, or stored client-side beyond the form's in-memory state.
- The Edit page is unchanged (no password management there).

## Capabilities

### New Capabilities

### Modified Capabilities
- `admin-host-employees`: the create page gains an optional password field with validation, and the create request carries it.

## Impact

- `src/domain/entities/host-employee-schema.ts` (`HostEmployeeCreateInput` gains `password`), `src/data/api/api-endpoints.ts` (`CREATE_STAFF_USER`).
- `src/infrastructure/host-employee-repository.ts` (`create` calls `/auth/users` after sync when a password is given).
- `src/presentation/pages/admin-host-employees/admin-host-employee-form.tsx` and `hooks/use-admin-host-employee-form.ts`.
- **Backend:** `POST /auth/users` (email, password 8-128 chars, fullName) is used. Whether it links to the employee created by sync, or errors on a duplicate email, is unverified and must be checked on stage.
