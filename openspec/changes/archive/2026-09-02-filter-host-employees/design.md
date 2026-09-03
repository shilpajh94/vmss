## Context

Every "Filters" button in the admin section (Buildings, Branches, Departments, Floors, Reception Desks, Security Gates, Visitor Categories, Workflows, Organisation Configs, Host Employees) is currently the same inert placeholder — there is no existing working-filter pattern anywhere in the codebase to follow. This is the first one, so the shape chosen here is worth documenting even though the change itself is small, since it may become the template other list pages copy later.

`useAdminHostEmployees` (`src/presentation/pages/admin-host-employees/hooks/use-admin-host-employees.ts`) already loads the full `hostEmployees` list and `departments` list on mount via `Promise.all(...)` — there is no pagination and no query-param support on `API_ENDPOINTS.LIST_HOST_EMPLOYEES` (`GET /auth/employees`, no filter params). `HostEmployee` carries `departmentId`, `isActive`, and `branchRoles: BranchRoleAssignment[]` (each with a `roleName`) directly.

## Goals / Non-Goals

**Goals:**
- Make "Filters" filter the Host Employees Directory by Department, Role, and Status.
- Keep filtering entirely client-side over data already in memory — no backend changes.

**Non-Goals:**
- Server-side filtering, pagination, or a query-param contract for `/auth/employees` — out of scope; revisit only if the employee list grows large enough that fetching it all client-side stops being viable.
- Establishing a shared/reusable "filter panel" component for other admin list pages — this change solves Host Employees only; extracting a shared component is a follow-up if/when a second page needs the same shape.
- "Import Hosts" — stays a non-functional placeholder, untouched by this change except that its requirement is split out from the one it used to share with Filters.

## Decisions

**Client-side filtering via `useMemo`, not a new endpoint.** The full employee list and department list are already fetched on mount; introducing server-side filtering would require a new query-param contract on `LIST_HOST_EMPLOYEES`, a repository/use-case signature change, and coordination with the backend for no real benefit at current data volumes. A `useMemo` deriving the filtered list from `hostEmployees` + three filter-state values is simpler, has zero network cost per filter change, and needs no data-layer changes at all.

**Filters apply immediately on change, no "Apply" button.** Since filtering is a pure client-side derivation with no network round-trip, there's no latency to batch against — applying live avoids an extra click and an extra piece of "pending vs applied" state to manage.

**Role options are derived from the loaded data, not a separate roles endpoint.** `listHostEmployeesUseCase` already returns each employee's `branchRoles[].roleName`; the Role filter's option list is the deduplicated set of role names actually present across the loaded employees (via a `useMemo` over `hostEmployees`), rather than fetching the full role catalog from `listRolesUseCase`/`HostEmployeeRepository.listRoles()` (used elsewhere for role management, not filtering) — this guarantees every option in the filter actually has at least one matching employee, so there's no dead "0 results" option to reach for by mistake, and avoids an extra network call this page doesn't otherwise make on load.

**Filter panel UI**: a simple inline panel (using the existing `SelectField` component, matching its look everywhere else in the app) that toggles open/closed under the "Filters" button, containing the three selects plus a "Clear filters" text action. No modal, no separate route/URL state — filters reset on navigating away and back, matching how every other piece of this page's local UI state behaves today (nothing on this page persists across navigations).

## Risks / Trade-offs

- [Risk] Deriving Role options only from currently-loaded employees means a role with zero employees currently assigned to it won't appear as a filter option → Mitigation: acceptable — filtering by a role nobody has would always return zero results anyway, so this is a feature (no dead options) not a gap.
- [Risk] Because filtering is purely client-side, it doesn't scale if the Host Employees list grows very large (hundreds+) → Mitigation: explicitly a non-goal here; flagged above as a follow-up trigger if/when it becomes a real problem.
