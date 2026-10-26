## Context

The Employees Directory (`admin-host-employees`) loads via `listHostEmployeesPageUseCase` → `HostEmployeeRepository.listPage` → `GET /auth/employees` with `page`, `pageSize`, `departmentId`, `role`, `status`. Filters live in `use-admin-host-employees.ts`, which resets the page on each change and polls every 15 s. The page has no search box. The invitations board already debounces search with `useDebouncedValue(search, 300)`.

## Goals / Non-Goals

**Goals:** server-side search on the directory page, combined with existing filters, with correct paging and empty states.

**Non-Goals:** searching phone/designation (backend doesn't), changing the unpaged `list()` or the public `/auth/employees/directory`, new endpoints, or client-side filtering.

## Decisions

- **Plumb `search?: string` through the existing layers** (port params → adapter `queryParams` → hook). No new use case or endpoint entry; `API_ENDPOINTS.LIST_HOST_EMPLOYEES` is unchanged. `makeRequest` already drops `undefined` query params, so a blank search sends nothing.
- **Debounce in the hook** with `useDebouncedValue(search, 300)` (the repo's existing pattern; 300 ms is within the requested 300–500 ms and keeps well under 60 req/min). The hook exposes the raw `search` for the input and uses the debounced, trimmed value for requests.
- **Reset page on change of the debounced value**, not per keystroke, so the page doesn't jump before a request is made. Done by calling `resetToFirstPage()` in an effect on the debounced value (skipping the initial mount), consistent with how filter setters call `resetToFirstPage`.
- **Search is not a "filter" for Clear filters.** Like the invitations board ("Leaves the search text alone"), clearing filters keeps the search text. `isFiltering` becomes `filters || debouncedSearch !== ''` only for choosing the empty-state message.
- **Search box in the header row** next to Filters / Add Employee, always visible (not inside the collapsible panel), using the same visual style as the board search field (`SearchGlyphIcon`, `h-10` bordered input), with `maxLength={255}`. A small inline component in the page's `Components/` folder avoids coupling to `BoardFilterBar`.
- **Polling** keeps using the current debounced search via `loadHostEmployees`'s dependencies, so background refreshes stay consistent with the visible results.
- **Stale responses:** `useLoadTracker`'s `request.succeed()` guard already discards superseded loads, so out-of-order responses can't overwrite newer search results.

## Risks / Trade-offs

- A 400 for >255 chars shouldn't occur thanks to `maxLength`; the existing generic load-error toast covers any other failure.
- Rate limit (60/min/IP): debounce plus 15 s polling is far below it.
- Adding the search box is UI scope inferred from "wire the search box" since none exists today; placement/styling is an assumption the reviewer can adjust.
