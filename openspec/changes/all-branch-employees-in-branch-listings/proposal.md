## Why

An employee who belongs to **all branches** is not returned by a branch-scoped
`GET /auth/employees` call. Today an employee is visible under a branch only if
their department sits at that branch or they hold a role grant at that branch
(or a company-wide `branch_id IS NULL` role grant). An employee with no
department and no branch-specific grant — i.e. mapped to every branch — appears
only in the unscoped listing. The visible symptom is the *Approve & Delegate*
dialog showing "No employees are eligible for the next step yet" (the
delegate-candidate lookup is `?role=…` with `X-Branch-ID`), and the same gap
hides these employees from the branch-filtered employee list where the
disable/delete actions live.

## What Changes

- A branch-scoped employee listing returns **the union of**: employees
  belonging to that branch (department at the branch, or a role grant at that
  branch), **and** every all-branch employee (no department / company-wide
  mapping).
- An all-branch employee appears in the listing of **every** branch, so the
  disable / enable / delete actions are reachable from any branch's view.
- An employee holding multiple roles (mix of branch-specific and all-branch
  grants) appears exactly once per page and is counted once in `total`.
- The `role` filter keeps working with the new rule, so delegate-candidate
  lookups (`?role=<step role>` + `X-Branch-ID`) include all-branch holders.
- No change to the unscoped listing, to authorization on disable/enable/delete
  (`employees:manage`), or to the response shape. Additive; no `v1` break.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `auth`: adds a requirement defining which employees a branch-scoped employee
  listing returns, including all-branch employees.

## Impact

- Code: `auth/repository.py::UserRepository.list_employees_page` (branch-scope
  clause), docstring in `auth/router.py::list_employees`.
- Tests: `auth/tests.py` — all-branch employee, multi-role no-duplicate,
  other-branch exclusion, `role` filter, tenant-isolation.
- Docs: `docs/features/auth.md` (listing rules).
- DB/migrations: none. APIs: behavior of an existing endpoint widens.
- Related: touches the same listing as the in-progress
  `employee-delete-disable-invitation-retention` change; no file conflicts
  beyond `auth/repository.py`.
