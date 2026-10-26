## 1. Backend

- [x] 1.1 Add `search: Annotated[str | None, Query(max_length=255)] = None` to `list_employees` in `auth/router.py` and update its docstring
- [x] 1.2 Thread `search` through `auth/service.py::list_employees` (trim; blank becomes `None`)
- [x] 1.3 Add `search` to `UserRepository.list_employees_page`: OR of `full_name`/`email`/`employee_code` `ilike` with escaped `%`/`_`, appended to the shared `conditions` list

## 2. Tests

- [x] 2.1 Test search by partial name, email fragment, and employee code (case-insensitive)
- [x] 2.2 Test `search` combined with `status`, `role`, and `X-Branch-ID` scope, and that `pagination.total` reflects the filtered set
- [x] 2.3 Test literal `%`/`_`, blank/whitespace `search`, and 256-char rejection

## 3. Docs

- [x] 3.1 Document the `search` param in `docs/features/auth.md`
- [x] 3.2 Run `ruff check`, `ruff format --check`, `mypy` on `auth/`, and `pytest`
