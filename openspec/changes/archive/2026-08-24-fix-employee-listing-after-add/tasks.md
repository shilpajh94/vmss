## 1. Schemas

- [x] 1.1 Add `EmployeeCreateRequest` to `auth/schemas.py`: `email`,
      `full_name`, `employee_code`, `department_id` (required), plus
      optional `phone_number` and `designation` — same field shapes as
      `EmployeeSyncItem`.

## 2. Service

- [x] 2.1 Add `create_employee(tenant_db, *, tenant_id, payload:
      EmployeeCreateRequest) -> User` to `auth/service.py`: checks
      `UserRepository.get_by_email` for a 409 on duplicate email (same as
      `register_user`), validates `payload.department_id` exists via
      `DepartmentRepository` for a 404 on missing department (same check
      `sync_employee_directory` does, single-id form), then calls the
      existing `create_user` helper with a random unusable password
      (`secrets.token_urlsafe(32)` through `hash_password`, same as sync)
      and the employee fields, commits, and returns the new `User`.

## 3. Router

- [x] 3.1 Add `POST /auth/employees` in `auth/router.py`, gated by
      `Depends(require_permission("employees:manage"))`, status 201,
      `response_model=Envelope[EmployeeOut]`.
- [x] 3.2 Call `service.create_employee`, return
      `success_response(data=_to_employee_out(new_employee),
      status_code=201)`.
- [x] 3.3 Record an `employee_created` audit log entry via
      `background_tasks.add_task(record_audit_log, ...)`, matching the
      pattern used by `create_user`/`sync_employee_directory`.

## 4. Tests (`auth/tests.py`)

- [x] 4.1 Happy path: create an employee with a valid `department_id`, assert
      201 and the returned fields match the request.
- [x] 4.2 Regression test for the reported bug: create an employee via
      `POST /auth/employees`, then call `GET /auth/employees` (scoped to
      that employee's branch) with no sync call in between, and assert the
      new employee is present.
- [x] 4.3 Assert creating one employee does not change any other existing
      employee's `is_active` status.
- [x] 4.4 Duplicate email returns 409 and does not create a row.
- [x] 4.5 Nonexistent `department_id` returns 404 and does not create a row.
- [x] 4.6 Permission-denied case: a caller without `employees:manage` gets
      403.
- [x] 4.7 Tenant-isolation case: an employee created in one tenant schema is
      not visible via `GET /auth/employees` under a different tenant's
      session (`make_tenant_schema`/`open_tenant_session` fixtures per
      `testing-standards.md` §2).

## 5. Documentation

- [x] 5.1 Update `docs/features/auth.md` with the new `POST /auth/employees`
      endpoint: request/response shape, required permission, and a note
      that it's the single-employee counterpart to the bulk
      `/auth/employees/sync` endpoint.
