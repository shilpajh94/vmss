## Why

The Employees Directory (admin) can only be narrowed by Department, Role, and Status; there is no way to find a person by name, email, or employee code. The backend now supports server-side search on `GET /auth/employees`, so the page can offer a search box that works across the whole roster (not just the loaded page).

## What Changes

- Add an optional `search` query param to the employees list request (`LIST_HOST_EMPLOYEES`), passed through the port, adapter, and use case.
- Add a search box to the Employees Directory header that sends the trimmed, debounced (300 ms) text as `search`.
- Reset to page 1 whenever the search text changes; `total`/pagination reflect the searched results.
- Combine search (AND) with the existing Department, Role, and Status filters.
- Show the existing "no match" empty state when a search (or filter) returns nothing.
- Cap input at 255 characters (the backend rejects longer values).
- Not changed: response shape, the unpaged `list()` call, the public `/auth/employees/directory` endpoint, phone/designation (not searchable server-side).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `admin-host-employees`: employee list gains a server-side search by name, email, or employee code that combines with the existing filters; the "no match" empty state also covers an active search.

## Impact

- `src/data/repositories/host-employee-repository.ts` (`ListHostEmployeesPageParams.search`)
- `src/infrastructure/host-employee-repository.ts` (`listPage` query params)
- `src/presentation/pages/admin-host-employees/` (`admin-host-employees.tsx`, `hooks/use-admin-host-employees.ts`)
- Reuses `useDebouncedValue`; no new dependencies, endpoints, or composition-root wiring.
- Backend contract: additive, existing calls unaffected; endpoint is rate-limited to 60 req/min per IP, hence the debounce.
