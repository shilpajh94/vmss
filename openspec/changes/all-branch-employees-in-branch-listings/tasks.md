## 1. Reproduce

- [x] 1.1 Add a failing test: employee with no department/grants is absent from a branch-scoped `GET /auth/employees`
- [x] 1.2 Confirm against the Approve & Delegate lookup (`role=<step role>` + `X-Branch-ID`) what shape the "all branch" employee has in the data

## 2. Implementation

- [x] 2.1 Extend the branch-scope clause in `auth/repository.py::list_employees_page` to include all-branch employees (design Decision 2)
- [x] 2.2 Update the `list_employees_page` and `list_employees` router docstrings to the new rule

## 3. Tests

- [x] 3.1 All-branch employee listed under two different branches
- [x] 3.2 Branch A scope returns A's employees + all-branch, excludes branch B's
- [x] 3.3 Multi-role employee appears once; `total` counts once
- [x] 3.4 `role=host` filter returns an all-branch holder
- [x] 3.5 Disable/enable/delete work on an all-branch employee viewed from another branch; permission-denied case
- [x] 3.6 Tenant-isolation case against a second tenant schema

## 4. Docs & Verify

- [x] 4.1 Update `docs/features/auth.md` listing rules
- [x] 4.2 Run `ruff check`, `ruff format --check`, `mypy` (auth/), and `pytest`
