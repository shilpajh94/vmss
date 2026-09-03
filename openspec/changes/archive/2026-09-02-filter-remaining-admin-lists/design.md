## Context

`filter-host-employees` (already implemented) established the pattern: filter state + a `useMemo`-derived filtered list live in the page's existing hook, options come from data already in memory, `SelectField` renders each filter, and a "Clear filters" action resets everything. See `openspec/changes/archive/` — no, it isn't archived yet — see the sibling change `filter-host-employees` for the full design rationale (client-side over server-side, live-apply over an "Apply" button, options derived from loaded data over a new endpoint). This change applies that same, already-decided pattern to 7 more pages; it does not revisit those decisions.

What's new here is that not every page already loads the reference-entity list its filter needs, the way Host Employees already loaded `departments`. The investigation found three buckets:
- **Already loaded, reuse directly**: `admin-floors` already loads both `listBuildingsUseCase` and `listDepartmentsUseCase`.
- **Not loaded, but the field is denormalized onto each row already**: `admin-departments` (`branchName` on each `Department`), `admin-buildings` (`branchName` on each `Building`), `admin-reception-desks` (`buildingName`/`floorName` on each `ReceptionDesk`), `admin-security-gates` (`buildingName` on each `SecurityGate`).
- **No reference entity needed at all** — the filter fields are enums/booleans on the entity itself: `admin-branches` (`isActive`), `admin-visitor-categories` (`badgeColor`, `ndaRequirement`, `escortRequirement`).

## Goals / Non-Goals

**Goals:**
- Working Filters on all 7 remaining admin list pages, each filtering on fields that mirror its own table columns.
- Zero new network calls beyond what each page already makes today.

**Non-Goals:**
- Revisiting the client-side-vs-server-side or live-vs-Apply-button decisions — already settled by `filter-host-employees`.
- Reconciling `admin-security-gates`' spec text describing a "connectivity status" (Online/Maintenance/Offline) and "auth method" that don't exist in the schema, hook, or table — that's a pre-existing drift unrelated to Filters; this change filters on the fields that actually exist (`gateType`, `highSecurity`) and leaves that drift for a separate change if it's ever addressed.
- Cascading filters (e.g. Reception Desks' Floor options narrowing based on the selected Building) — each filter field is independent; selecting a Building doesn't currently limit the Floor dropdown's options. Simpler and consistent with every filter elsewhere being independent; can be revisited if the flat list becomes confusing in practice.
- A Department filter on `admin-floors` — floors carry a multi-valued list of departments (`departmentNamesByFloorId`), which doesn't fit the single-select filter pattern used everywhere else; left out rather than force-fit a multi-select just for this one page.

## Decisions

**Derive filter options client-side from denormalized fields already on each loaded row, rather than adding a new `listBranchesUseCase`/`listBuildingsUseCase`/etc. call to pages that don't already load it.** E.g. `admin-departments`' Branch filter options come from `new Set(departments.map(d => d.branchName))`, not a separate branches fetch — exactly the technique Host Employees already uses for its Role filter options (`roleOptions` derived from loaded `branchRoles`, not a `listRoles` call). This keeps every one of the 7 pages at its current number of network requests, and guarantees every filter option actually has at least one matching row (no dead "0 results" options).

**`admin-security-gates`'s "Security Level" filter is a derived boolean-as-select**, not a new field: `highSecurity: boolean` becomes a 2-option Status-shaped filter (High Security / Standard), consistent in shape with every other `SelectField`-based filter in this change rather than a one-off checkbox.

**Each page keeps its own independent hook/component changes** — there is no shared "filter panel" component extracted across the 7 pages in this change (same non-goal call made in `filter-host-employees`'s design doc; a shared component is a follow-up if a second concrete need for one shows up, not before).

## Risks / Trade-offs

- [Risk] Deriving options from currently-loaded rows means a reference value with zero current rows (e.g. a Branch with no Departments yet) won't appear as a filter option → Mitigation: same accepted trade-off as Host Employees' Role filter — filtering by something with zero matches would always return zero results anyway.
- [Risk] Seven pages' hooks and components all change in this one batch, increasing the surface reviewed at once compared to doing them one at a time → Mitigation: each page's change is small and mechanically identical to the already-proven Host Employees pattern; tasks.md is organized per-page so review/rollback can still happen at page granularity if needed.
