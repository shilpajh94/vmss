## Context

See `proposal.md` for the "why". Relevant existing code:

- `auth/service.py::create_user` already accepts `employee_code`,
  `designation`, `phone_number`, `department_id` as optional kwargs — it's
  the same helper `register_user` (backs `POST /auth/users`) and
  `sync_employee_directory` (backs `POST /auth/employees/sync`) both call.
  Only `sync_employee_directory` currently passes the employee-specific
  kwargs.
- `auth/repository.py::list_employees_page` requires `employee_code IS NOT
  NULL` and inner-joins `Department -> Floor -> Building`, so an employee row
  needs both fields set to ever appear in `GET /auth/employees`.
- `sync_employee_directory` validates every `department_id` it's given
  against `DepartmentRepository.get_existing_ids` before writing anything.

## Goals / Non-Goals

**Goals:**
- One employee can be created in one call, visible in the listing right
  after, without touching any other employee's state.
- Reuse `create_user`'s existing employee-field handling rather than
  duplicating it.

**Non-Goals:**
- Changing `POST /auth/users` or `POST /auth/employees/sync` behavior.
- Changing `list_employees_page`'s branch-scope/department-join rules —
  callers of the new endpoint still need to pass a valid `department_id` to
  have the employee show up in a branch-scoped listing, same as sync today.
- Issuing real login credentials to the new employee — same as sync, a
  password-reset/credential-issuance flow is a separate future feature.

## Decisions

- **New route, not an extension of `POST /auth/users`**: keeps
  `UserCreateRequest`/`POST /auth/users` scoped to admin/security accounts
  (its existing, documented meaning) and keeps the employee-shaped payload
  (`employeeCode`, `departmentId`, `phoneNumber`, `designation`) next to the
  other employee endpoints (`/employees/sync`, `/employees`). Alternative
  considered (adding optional employee fields to `UserCreateRequest`) was
  rejected per the confirmed fix approach — it would overload one endpoint
  with two different semantic outcomes based on which optional fields are
  present, which is harder for API consumers (and this file's own
  `response_model` docs) to reason about than a second explicit route.
- **`department_id` required, not optional**: `EmployeeSyncItem.department_id`
  is optional today, but an employee with no department can never appear in
  `list_employees_page`'s inner join. Since the entire point of this new
  endpoint is "visible in the listing right away," making `department_id`
  required on `EmployeeCreateRequest` closes that footgun for the one-shot
  path (sync's optional field stays as-is — out of scope here, and batch
  sync has legitimate bulk-import cases where department mapping arrives
  later).
- **New `service.create_employee` wraps `create_user`, not a copy of
  `sync_employee_directory`'s loop body**: sync's function handles N items,
  deactivation, and duplicate-code batch conflicts — none of which apply to
  a single create. `create_employee` only needs: email-uniqueness check
  (same as `register_user`), department-existence check (same single-id
  version of sync's validation), then one `create_user` call and commit.
- **Permission: `employees:manage`**, same as sync — creating an employee is
  the same privilege tier as bulk-syncing them; no new permission code is
  introduced.
- **Random unusable password**, same as sync (`secrets.token_urlsafe(32)`
  through `hash_password`) — consistent with "sync/create only manages
  directory data, never credentials" from `sync_employee_directory`'s
  docstring.

## Risks / Trade-offs

- [Two employee-creation code paths (single-create and sync) diverging over
  time if one is changed without the other] → Both call the shared
  `create_user` helper for the actual row construction; only the
  validation/looping wrapper differs. A future field addition to `User`'s
  employee columns still only needs one change in `create_user`.
- [`employee_code` uniqueness isn't enforced at the single-create layer
  before hitting the DB, same gap as sync today] → Out of scope for this
  change; matches existing behavior (`IntegrityError` → `409` in sync). Not
  worsened by this change.
