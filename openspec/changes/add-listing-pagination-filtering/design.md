## Context

See `proposal.md` - Why/Impact. The shared pagination plumbing
(`core/deps.py::get_pagination`, `core/schemas.py::PaginationMeta`/
`PaginatedEnvelope`, `core/responses.py::paginated_response()`) already
exists and is exercised by `GET /auth/roles`, `org_structure`, `visitors`,
`invitations`, and `audit_trail`. The `auth/permissions` piece of this
change is narrow: point `GET /auth/permissions` at that same plumbing
instead of introducing anything new.

The filter-addition piece (org_structure/visitors) was discovered
mid-implementation of the paired `improve-listing-ux` web change: its list
pages need to send Status/Access Level/Gate Type/Security Level/Badge
Color/NDA/Escort as query params, but the corresponding API endpoints only
accepted parent-scope filters (`buildingId`, `floorId`) and pagination/sort
— not these attribute filters. Every affected repository already uses
`TenantScopedRepository.paginate(filters=[...])` or an equivalent manual
count+page query (see `org_structure/repository.py`), so adding a filter is
mechanically the same pattern already used for `buildingId`/`floorId` — an
optional `Query()` param, translated to a SQLAlchemy `WHERE` clause,
appended to that repository method's existing `filters` list.

## Goals / Non-Goals

**Goals:**
- Bring `GET /auth/permissions` in line with the `PaginatedEnvelope` shape
  every other compliant list endpoint already returns.
- Land the response-shape change and its one consuming client (the web
  role-permission-edit page, in the paired `improve-listing-ux` change)
  together, so there's no window where the API has changed shape but no
  client has been updated to match.

**Non-Goals:**
- Building a baseline spec for `platform`/`sso` (no capability spec exists
  for either yet) or touching the in-flight `form-builder` change's
  endpoints — both are out of scope per `proposal.md`'s Impact section.
- Introducing any new filter field on the permission catalog. It stays
  filterless like `GET /auth/roles`; only pagination and sort are added.

## Decisions

- **Reuse `get_pagination`/`PaginatedEnvelope` as-is rather than a
  catalog-specific pagination helper.** The permission catalog has no
  properties (tenant-independent size, no filters) that would justify a
  bespoke shape, and reuse keeps every list endpoint's client-side handling
  identical. Alternative considered: a lighter "just add a `total` count to
  the existing bare envelope" — rejected because it produces a third
  response shape family instead of converging on the one convention already
  used by four other features.
- **Default page size 20, matching every other compliant endpoint**, not a
  larger default just because the catalog is currently small. A future
  catalog growth doesn't require revisiting this endpoint's defaults if they
  already match the house convention.
- **Sort whitelist limited to `code`.** The catalog has no other
  sortable, meaningful field today (no display name, no category grouping
  column exists in the model); adding a whitelist entry for a field that
  doesn't exist yet would be speculative.
- **New filter enums live in each feature's own `schemas.py`, not a shared
  `core` module**, mirroring how `DeskStatus`/`GateType` already live in
  `org_structure/schemas.py` rather than `core/schemas.py`. `ActiveStatus`
  (branches/buildings/floors/departments) and `SecurityLevel`
  (security gates) are new to `org_structure`;
  `ApprovalWorkflowRuleStatus` is new to `visitors` — kept separate from
  `org_structure.ActiveStatus` even though both are "active/inactive"
  string enums, to avoid a cross-feature import for one small enum
  (`fastapi-architecture.md` §6's "core doesn't depend on features" spirit
  applied one level down: features don't reach into each other's schemas
  either).
- **`securityLevel` and the desk/rule "status" filters map onto existing
  boolean or differently-named columns rather than adding new columns.**
  `SecurityGate.high_security` (bool) becomes `standard`/`high`;
  `ApprovalWorkflowRule.is_active` becomes `active`/`inactive` — consistent
  with how the UI already presents these as named states, without a
  migration.
- **Router-level filter parameter names avoid shadowing FastAPI's `status`
  module import.** Every GET handler in `org_structure/router.py` already
  uses `status.HTTP_201_CREATED` etc. in sibling functions; naming a query
  param `status` directly would shadow that import within the function it's
  declared in. Each endpoint instead takes an entity-prefixed local name
  (`branch_status`, `building_status`, `floor_status`, `department_status`,
  `desk_status`) while keeping the wire-level query param itself named
  `status` via `Query(alias="status")`, so the API contract is unaffected.

## Risks / Trade-offs

- [The response-shape change is breaking for any caller reading `data` as a
  flat array] → The only current consumer is the web admin's
  role-permission-edit page, updated in the paired `improve-listing-ux`
  change in the same release. No other known caller exists (confirmed via
  the codebase audit backing this proposal — `platform`/`sso` list a
  different catalog shape entirely and are unaffected).
- [A caller that paginates and stops at page 1 could silently miss
  permissions added after their form loaded, if the catalog grows past 20
  entries between login and use] → Pre-existing risk shared by every other
  paginated catalog-style endpoint (`roles`); not something this change
  makes worse, since the alternative (no pagination) has the opposite,
  worse failure mode of an ever-growing single response.

## Migration Plan

1. Land this change's API-side edits first (endpoint, schema, tests) —
   both the `auth/permissions` pagination piece and the org_structure/
   visitors filter-addition piece, since the paired web change's list
   pages depend on the filters existing before they can send them.
2. Land the corresponding web-side edits (paired `improve-listing-ux`
   change): the `admin-roles` capability delta reading `data.data` +
   `data.pagination` instead of `data` directly, and every list page that
   now sends a Status/Access Level/Gate Type/Security Level/Badge Color/
   NDA/Escort filter as a query param.
3. No data migration or backfill is needed for either piece — these are
   response-shape and filter-parameter additions on read endpoints, not
   schema changes.
4. Rollback is a revert of the relevant API commit(s); the web change's
   updated client code only works against the new filter params and
   `PaginatedEnvelope` shape, so both changes should deploy and roll back
   together, not independently.
