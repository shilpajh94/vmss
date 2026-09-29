## Why

A codebase-wide audit of every `GET` collection endpoint found that
`org_structure`, `visitors`, `invitations`, and `audit_trail` already follow
`api-conventions.md` §1's *pagination* shape in full (`page`/`page_size`,
`sort_by`/`sort_order`, and the `PaginatedEnvelope` response shape). Two
gaps remained, one found at proposal time and one found mid-implementation:

1. `GET /auth/permissions` still returned a bare `Envelope[list[PermissionOut]]`
   with no pagination metadata and no `sort_by`/`sort_order`, unlike its
   sibling `GET /auth/roles`, which was already compliant.
2. The pagination audit didn't check *filtering* closely enough: six
   `org_structure` list endpoints (branches, buildings, floors, departments,
   reception desks, security gates) and two `visitors` list endpoints
   (visitor categories, approval workflow rules) only supported
   parent-scope filters (e.g. `buildingId`, `floorId`) — not the
   status/type/attribute filters (Status, Access Level, Gate Type, Security
   Level, Badge Color, NDA/Escort Requirement) the paired web-side change
   (`improve-listing-ux` in `VMMS_WEB`) needs to send server-side. This
   surfaced only once that change's list pages were actually wired up to
   request filtered pages — see its `design.md` for how the gap was found.

## What Changes

- `GET /auth/permissions` gains `page`/`page_size` query params (defaults:
  page 1, page size 20, max 100) and `sort_by`/`sort_order` (whitelisted to
  `code`, default `code` ascending), and its response switches from a bare
  `Envelope[list[PermissionOut]]` to `PaginatedEnvelope[PermissionOut]` — the
  same shape `GET /auth/roles` already returns. **BREAKING**: any caller
  currently reading `data` as the full permission list must read
  `data.pagination.total`/`totalPages` and page through results; the
  catalog is small today, so this is the right moment to make the contract
  correct before a caller starts relying on "the array is everything."
- `GET /branches` gains `?status=active|inactive`.
- `GET /buildings` gains `?status=active|inactive`.
- `GET /floors` gains `?status=active|inactive` and
  `?accessLevel=public|restricted|secure`.
- `GET /departments` gains `?status=active|inactive`.
- `GET /reception-desks` gains `?status=active|maintenance|inactive`
  (`DeskStatus`, already the model's own three-state enum).
- `GET /security-gates` gains `?gateType=entry|exit|both` and
  `?securityLevel=standard|high` (mapped onto the existing `high_security`
  boolean).
- `GET /visitor-categories` gains `?badgeColor=`, `?ndaRequirement=`, and
  `?escortRequirement=`.
- `GET /approval-workflow-rules` gains `?status=active|inactive` (mapped
  onto the existing `is_active` column; `?visitorCategoryId=` already
  existed).
- `GET /employees` gains `?status=active|inactive` (mapped onto
  `User.is_active`; `departmentId`/`email`/`role` already existed).
- `GET /invitations` gains `?search=` (case-insensitive substring match
  against `primaryContactFullName` OR `trackingId`).
  All additive: none of these change an existing response shape or an
  existing param's meaning, so none are breaking on their own.
- **Correction, not addition**: the paired web change's original plan
  included a "Status" filter on the admin Roles page. `Role` has no
  active/inactive concept in this system (only a computed Standard/Custom
  distinction based on name) — there is no column to filter on. No API
  change was made for this; the web change's `admin-roles` spec delta was
  corrected to drop the Status filter rather than adding an unjustified
  `is_active` column to `Role` with no product requirement behind it.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `auth`: `GET /auth/permissions` gains pagination and sort parameters and
  returns `PaginatedEnvelope[PermissionOut]` instead of a bare list envelope.
- `org-structure`: `GET /branches`, `/buildings`, `/floors`, `/departments`,
  `/reception-desks`, and `/security-gates` gain the typed filter query
  params listed above.
- `visitors`: `GET /visitor-categories` and `/approval-workflow-rules` gain
  the typed filter query params listed above.
- `auth`: `GET /employees` gains a `status` filter, in addition to the
  `GET /auth/permissions` pagination change already described above.
- `invitations`: `GET /invitations` gains a `search` filter (case-insensitive
  substring match against `primaryContactFullName` OR `trackingId`) —
  discovered the same way as the others: the paired web change's Invitations
  board search box had no server-side equivalent to send to.

## Impact

- **Code**: `src/vmss_api/auth/router.py` (`list_permissions`, currently
  line 409), `src/vmss_api/auth/schemas.py` (response model), and
  `src/vmss_api/auth/service.py`/`repository.py` if the catalog read needs a
  `LIMIT`/`OFFSET`-aware query. Reuses existing shared plumbing —
  `core/deps.py::get_pagination`, `core/schemas.py::PaginationMeta` /
  `PaginatedEnvelope`, `core/responses.py::paginated_response()` — no new
  infrastructure required.
- **Code (filters)**: `src/vmss_api/org_structure/{router,service,repository,schemas}.py`
  (new `ActiveStatus`/`SecurityLevel` enums; `list_page` methods on
  `BranchRepository`, `BuildingRepository`, `FloorRepository`,
  `DepartmentRepository`, `ReceptionDeskRepository`, `SecurityGateRepository`
  gain new filter parameters) and
  `src/vmss_api/visitors/{router,service,repository,schemas}.py` (new
  `ApprovalWorkflowRuleStatus` enum; `VisitorCategoryRepository.list_page`
  and `ApprovalWorkflowRuleRepository.list_page` gain new filter
  parameters). All additive query params on already-paginated endpoints —
  no response-shape change, no `TenantScopedRepository.paginate()` changes.
- **Clients**: any admin-portal or future integration code that currently
  reads `GET /auth/permissions`' `data` as a flat array (e.g. a role-editor
  permission picker) must be updated to read `data.data` plus
  `data.pagination`. The paired web-side change (`improve-listing-ux` in
  `VMMS_WEB`) is the one place today that consumes this endpoint's shape and
  will be updated alongside this one.
- **Explicitly out of scope, with reasons** (surfaced by the same audit, not
  overlooked):
  - `GET /platform/tenants` and `GET /sso/role-mappings` — both already defer
    pagination in-code with a comment citing `api-conventions.md` §2's
    breaking-change concern, and neither `platform` nor `sso` has a baseline
    spec capability yet. Adding pagination here would mean writing that
    capability's full baseline spec from scratch as a side effect of a
    pagination fix, which is a bigger, separate undertaking — flagged as a
    follow-up change, not folded into this one.
  - `GET /form_builder/steps` and `GET /form_builder/steps/{step_id}/fields`
    — the `form-builder` capability path is already claimed by an in-flight,
    unarchived change (`openspec/changes/form-builder/`). A competing delta
    spec for the same capability from this change would clash with it;
    pagination for these endpoints belongs in that change instead.
  - `GET /dashboard/search`, `GET /visit-info/hosts/search`,
    `GET /visit-info/departments`, `GET /visit-info/options` — these are
    typeahead/autocomplete and bounded-catalog lookups (capped result counts,
    no "next page" UX in any client), not paged listings in the sense
    `api-conventions.md` §1 describes. Forcing `page`/`page_size` onto them
    would add ceremony a search-as-you-type or kiosk dropdown never uses.
