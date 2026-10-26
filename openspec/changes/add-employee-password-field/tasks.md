## 1. Contract

- [x] 1.1 Checked backend OpenAPI: sync has no password; `POST /auth/users` takes email/password(8-128)/fullName
- [x] 1.2 Add `CREATE_STAFF_USER` (`POST /auth/users`) to `API_ENDPOINTS`
- [x] 1.3 Add optional `password` to `HostEmployeeCreateInputSchema` in `src/domain/entities/host-employee-schema.ts`

## 2. Adapter

- [x] 2.1 In `HttpHostEmployeeRepository.create`, before the sync, call `CREATE_STAFF_USER` with email/password/fullName when a password was entered

## 3. Form hook

- [x] 3.1 Add `password: undefined` to `EMPTY_CREATE_VALUES` in `use-admin-host-employee-form.ts`
- [x] 3.2 In `submitCreate`, validate: if password non-empty and < 8 chars, set `createErrors.password`

## 4. UI

- [x] 4.1 Add masked Password field with show/hide toggle (`autoComplete="new-password"`) to create mode of `admin-host-employee-form.tsx`; not shown in edit mode
- [x] 4.2 Show the validation error under the field

## 5. Verify

- [ ] 5.1 Add/update unit tests — skipped: project has no test runner or existing tests
- [ ] 5.2 Manually verify on stage (incl. that /auth/users works for a sync-created email, and the new employee can log in): blank, short, valid password, toggle, and that edit page has no field
