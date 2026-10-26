## Why

The admin portal's Employees Directory lists employees through `GET /auth/employees`,
which only supports exact-match filters (`departmentId`, `email`, `role`, `status`).
An admin looking for a person by name, a partial email, or an employee code has no
way to find them except paging through the list. A search field in the directory
needs a server-side `search` filter, since the listing is paginated and the client
only ever holds one page.

## What Changes

- `GET /auth/employees` gains an optional `search` query param (max 255 chars).
  It matches case-insensitively as a substring against the employee's full name,
  email, and employee code.
- `search` composes (AND) with every existing filter, branch scope, sorting and
  pagination; `pagination.total`/`totalPages` reflect the searched result set.
- Blank or whitespace-only `search` is treated as absent. `%` and `_` in the term
  are matched literally, not as wildcards.
- Additive only; no change to the response shape or existing params, so no
  `/api/v2` bump is needed (`api-conventions.md` §2).
- Assumption: "search field in admin login" means the search box on the Employees
  Directory page of the admin portal (after admin sign-in). The React portal change
  is a separate repo and out of scope here.

## Capabilities

### New Capabilities

### Modified Capabilities
- `auth`: the employee directory listing gains a free-text search filter.

## Impact

- `src/vmss_api/auth/router.py` (`list_employees` query param), `auth/service.py`
  (`list_employees` pass-through), `auth/repository.py`
  (`UserRepository.list_employees_page` condition).
- `auth/tests.py` (happy path, combination with filters, wildcard escaping).
- `docs/features/auth.md` (document the param).
- No migration, no new setting, no new permission (the endpoint's existing
  public/rate-limited access model is unchanged).
