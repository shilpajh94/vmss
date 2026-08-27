## Why

`GET /auth/employees` only returns rows where `employee_code` is set and
`department_id` resolves to a branch (`auth/repository.py::list_employees_page`
inner-joins `Department -> Floor -> Building`). Today the only endpoint that
sets those fields is `POST /auth/employees/sync`, which treats its payload as
the *entire* authoritative employee directory and deactivates every existing
employee whose code is missing from the batch. There is no endpoint to add
one employee: `POST /auth/users` creates a generic admin/security account
with `employee_code`/`department_id` left `NULL` by design, so a user added
through it never appears in the employee listing. The frontend team has
worked around this by calling the sync endpoint after adding an employee,
which is both a confusing extra step and risky — a sync batch that omits an
existing employee's code silently deactivates that employee.

## What Changes

- Add `POST /auth/employees` — creates a single employee directly, setting
  `employee_code`, `department_id`, `phone_number`, and `designation` on
  creation (mirroring `sync_employee_directory`'s per-item create logic), so
  the new employee is immediately visible via `GET /auth/employees` with no
  follow-up sync call required.
- `POST /auth/users` is unchanged — it continues to create non-employee
  admin/security accounts only.
- `POST /auth/employees/sync` is unchanged — bulk reconcile semantics stay as
  documented.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `auth`: adds a requirement that a single employee can be created directly
  (without a full directory sync) and is immediately visible in the employee
  listing.

## Impact

- `src/vmss_api/auth/schemas.py`: new `EmployeeCreateRequest` request schema.
- `src/vmss_api/auth/service.py`: new `create_employee` service function
  (thin wrapper around the existing `create_user` helper, reusing its
  email-uniqueness and employee-field handling).
- `src/vmss_api/auth/router.py`: new `POST /employees` route, gated by the
  existing `employees:manage` permission (same as sync), with an
  `employee_created` audit log entry.
- `src/vmss_api/auth/tests.py`: happy path, permission-denied, and
  tenant-isolation coverage for the new endpoint, plus a regression test that
  an employee created this way appears in `GET /auth/employees` without a
  sync call.
- `docs/features/auth.md`: document the new endpoint.
- No database migration — reuses existing `User` columns.
