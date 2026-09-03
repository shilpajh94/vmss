## Why

`filter-host-employees` made "Filters" actually work on the Host Employees Directory. The admin wants the same treatment everywhere else — every other admin list page's "Filters" button is still the same inert placeholder.

## What Changes

Apply the same working-filter pattern (client-side, live-updating `useMemo` over the already-loaded list, using the existing `SelectField` component, with a "Clear filters" action, and a distinct "no matches" empty state) to the remaining 7 admin list pages. Filter fields are chosen to mirror each page's own table columns, same as Department/Role/Status mirrored the Host Employees table:

| Page | Filter fields |
|---|---|
| Branches | Status |
| Departments | Branch, Status |
| Buildings | Branch, Status |
| Floors | Building, Access Level, Status |
| Reception Desks | Building, Floor, Status |
| Security Gates | Building, Gate Type, Security Level (High Security / Standard) |
| Visitor Categories | Badge Color, NDA Requirement, Escort Requirement |

- Where a page doesn't already load the reference entity list it needs (e.g. Departments needs Branch names but doesn't load `listBranchesUseCase`), filter options are derived client-side from the already-loaded list's own denormalized name fields (e.g. `department.branchName`) — same technique Host Employees' Role filter already uses — rather than adding a new use-case call. See design.md.
- **Out of scope**: Departments and Reception Desks/Security Gates tables show a `Department(s)` / assigned-receptionist-style column that's either multi-valued or not a clean enum — these are not added as filters (matches the reasoning that excluded a similar case from the Host Employees change).
- **Out of scope, flagged explicitly**: `admin-security-gates`' current spec describes a three-state "connectivity status" (Online/Maintenance/Offline) and an "auth method" that do not exist anywhere in the actual schema, hook, or table (only `gateType` and `highSecurity` are real fields) — this is a pre-existing spec/implementation gap unrelated to Filters. This change filters by the fields that actually exist (`gateType`, `highSecurity`) and does not attempt to reconcile that unrelated drift.
- "Visitor Categories" has no `isActive`/status field on its entity at all, so no Status filter is added there (its filters are Badge Color, NDA Requirement, Escort Requirement only, matching what the entity actually has).

## Capabilities

### Modified Capabilities
- `admin-branches`: "Filters affordance is presented but not yet functional" → working Status filter.
- `admin-departments`: → working Branch + Status filters.
- `admin-buildings`: → working Branch + Status filters.
- `admin-floors`: → working Building + Access Level + Status filters.
- `admin-reception-desks`: → working Building + Floor + Status filters.
- `admin-security-gates`: → working Building + Gate Type + Security Level filters.
- `admin-visitor-categories`: → working Badge Color + NDA Requirement + Escort Requirement filters.

## Impact

- Seven pages' `hooks/use-admin-*.ts` files gain filter state, a `useMemo`-derived filtered list, and (where needed) a client-side-derived options list from already-loaded data.
- Seven pages' `admin-*.tsx` files gain a filter panel (reusing `SelectField`) wired to the existing "Filters" button, and a distinct "no matches" empty state alongside each page's existing "zero records" empty state.
- No new API endpoints, no new use-cases, no domain schema changes — every filter operates on data the page already fetches (either directly or via reference lists already loaded elsewhere on the same page, or derived from denormalized fields already present on each row).
