## Context

This change touches three existing feature packages (`auth`, `org_structure`,
`visitors`), each already following the repository pattern
(`TenantScopedRepository` + `_NOT_DELETED` partial-unique-index convention)
described in `database-architecture.md`. `Role` (`auth/models.py`) already
inherits `Base, TimestampMixin`, so it already has `deleted_at` — no schema
change is needed to make it soft-deletable, only new repository/service/router
code. `RoleRepository` (`auth/repository.py:121`) already exists with
`get_by_name`, used today only internally by branch-role assignment; this
change extends it into a full CRUD repository and exposes it over HTTP.

Two of the field additions are genuine column-type changes on live tables
(`ReceptionDesk.is_active` → `status`, `SecurityGate.is_active` →
`connectivity_status`), not pure additions — see Decision 3 for how existing
`true`/`false` data maps onto the new tri-state values.

See proposal.md for motivation and the three spec deltas for the full
requirement text.

## Goals / Non-Goals

**Goals:**
- Give tenants a way to define roles beyond the fixed five, without breaking
  the existing guarantee that Admin/Reception/Security/Host/Visitor always
  exist with predictable names.
- Close the field gaps identified in the admin-portal design review so the
  web team's forms have somewhere to write the values they collect.
- Do all of this as additive/backward-compatible schema changes wherever
  possible, isolating the two genuine breaking changes (ReceptionDesk and
  SecurityGate status) to their own reviewed migration steps.

**Non-Goals:**
- Building any of the six subsystems listed under proposal.md's "Not in
  Scope" (check-in, SSO, form-builder, person-based workflow approvers,
  audit-trail read API, invitations dashboard).
- Changing how `require_permission`/`require_branch_permission` resolve
  permissions — custom roles plug into the exact same `UserBranchRole` /
  `has_permission` mechanism standard roles already use; no new access-control
  code path is introduced.
- Resolving the Department branch/floor hierarchy question with a schema
  redesign — `floor_id` stays as an optional secondary association, per the
  scope decision in proposal.md, rather than removing it.

## Decisions

### Decision 1: Standard roles are protected by name, not by a new `is_system` column
Rather than adding an `is_system: bool` column to `Role` to distinguish
seeded roles from custom ones, the service layer checks membership in the
existing `ROLE_PERMISSIONS` dict's key set (`auth/rbac_catalog.py`) before
allowing a rename or delete. **Why**: the five standard names are already the
single source of truth for what gets seeded; a second column would be a
second place that list has to stay in sync, and a tenant could in principle
rename a custom role to collide with a standard name only by first colliding
with the uniqueness constraint on `Role.name`, which the check runs against
regardless of column presence. **Alternative considered**: an `is_system`
column — rejected as redundant state that can drift from the catalog list.

### Decision 2: Role permission-set update replaces, not merges
`PUT /auth/roles/{id}` takes the role's full new permission-code list and
replaces `role_permissions` rows for that role wholesale (delete-then-insert
in one transaction), matching the existing full-replace convention used by
`VisitorCategory.form_schema` updates rather than introducing a separate
add-permission/remove-permission pair of endpoints. **Why**: keeps the API
surface small and matches this codebase's existing update semantics for
list-valued fields; a caller that only wants to add one permission still
sends the full list, same as editing a category's form schema today.

### Decision 3: ReceptionDesk/SecurityGate boolean-to-tri-state migration
`is_active: bool` becomes `status: str` (`active`/`maintenance`/`inactive`)
on `ReceptionDesk`, and `is_active: bool` becomes
`connectivity_status: str` (`online`/`maintenance`/`offline`) on
`SecurityGate` — new columns, not a repurposed boolean, so the migration is
reviewable as an explicit add-populate-drop sequence:
1. Add the new nullable string column.
2. Backfill: `true` → `active`/`online`, `false` → `inactive`/`offline`
   (single `UPDATE`, per `query-performance.md` §3 — no per-row loop).
3. Make the column non-nullable with its default, drop `is_active`.

Both new columns are plain `String` (checked at the API/Pydantic boundary via
an enum), matching this codebase's existing `SecurityGate.gate_type` pattern
(`org_structure/models.py:181`'s docstring: "kept as a plain string... rather
than a DB-level enum, to keep this migration a single `CREATE TABLE`") rather
than introducing this project's first native Postgres enum type.

### Decision 4: Department gets a direct `branch_id`, `floor_id` becomes optional
Per the confirmed scope decision, `Department.floor_id` changes from
`Mapped[uuid.UUID]` to `Mapped[uuid.UUID | None]`, and a new
`Mapped[uuid.UUID]` `branch_id` FK to `Branch` is added, not nullable — every
department has a branch (directly, or previously indirectly via its floor).
The uniqueness index moves from `(floor_id, code)` to `(branch_id, code)`
scoped to non-deleted rows, since the design's create flow scopes uniqueness
by branch, not floor. For existing rows created before this change (all of
which have a `floor_id`), the migration backfills `branch_id` by resolving
`floor_id → building_id → branch_id` in one `UPDATE ... FROM` join — no
existing department loses its branch/floor association.

**Risk**: two departments in different floors of the same branch that
already share a `code` (previously legal, since uniqueness was per-floor) 
will collide under the new per-branch uniqueness constraint. See Risks below.

### Decision 5: `roles:manage`/`roles:view` are new permission codes, not reuse of `users:manage`
Role CRUD gets its own permission codes in `rbac_catalog.py.PERMISSION_CODES`,
separate from the existing `users:manage` (which gates user creation and
branch-role *assignment*). **Why**: a tenant may reasonably want an admin who
can assign existing roles to users (`users:manage`) without being able to
redefine what those roles grant (`roles:manage`) — conflating the two would
remove that separation. Only the seeded `admin` role is granted
`roles:manage`/`roles:view` by default, same as every other management
permission in the catalog.

## Risks / Trade-offs

- **[Risk]** Existing departments sharing a `code` across different floors of
  the same branch will violate the new `(branch_id, code)` unique index.
  → **Mitigation**: the migration's backfill step includes a pre-check query
  that surfaces any such collisions before the constraint is added; if any
  exist, the migration halts with a report of the colliding rows for a human
  to rename one of them, rather than silently failing partway through
  `alembic upgrade`.
- **[Risk]** Loosening "exactly five standard roles" to "at least five,
  plus custom roles" changes an accepted spec requirement that other code
  (`docs`, tests) may cite as "five roles" in prose.
  → **Mitigation**: `auth/tests.py` gets an explicit test asserting the five
  seeded roles still exist and are non-deletable, so the *guarantee* the old
  wording protected is still verified even though the requirement text
  changes.
- **[Trade-off]** Full-replace semantics for role permission updates
  (Decision 2) mean a client must always fetch-then-submit-full-list rather
  than patching one permission, which is slightly more chatty for a
  single-permission toggle in the admin UI.
  → Accepted: consistent with this codebase's existing pattern elsewhere, and
  role permission sets are small (dozens of codes at most).

## Migration Plan

1. `alembic_tenant/versions/`: one migration per logical grouping (can be
   authored as separate files, applied together to every tenant schema per
   `database-architecture.md` §5 — there is no per-tenant autogenerate loop,
   these are authored once and applied to every existing tenant schema):
   - Branch/Building new columns + creation-time `is_active` (additive only).
   - Floor new columns (additive only).
   - Department: add `branch_id` nullable → backfill via
     `floor → building → branch` join → collision pre-check →
     add `(branch_id, code)` partial unique index → make `branch_id`
     non-nullable → make `floor_id` nullable → drop old
     `(floor_id, code)` index.
   - ReceptionDesk: add `status` + new columns → backfill from `is_active` →
     drop `is_active`.
   - SecurityGate: add `connectivity_status`, `high_security`, `auth_method`
     → backfill `connectivity_status` from `is_active` → drop `is_active`.
   - Company: add new policy columns (additive only, all nullable with
     sensible defaults so an existing single-row `Company` doesn't need a
     backfill decision).
   - VisitorCategory: add new columns (additive only).
2. `rbac_catalog.py`: add `roles:manage`/`roles:view` to `PERMISSION_CODES`
   and to the `admin` role's grant list; `seed_default_roles` is already
   idempotent (check-before-insert), so re-running it against an existing
   tenant schema adds the two new permission rows without touching existing
   roles.
3. Deploy code (new endpoints, updated schemas) after migrations have run
   against every existing tenant schema — an old code version talking to a
   migrated schema still works (new columns are additive or backfilled with
   safe defaults); a new code version talking to an unmigrated schema would
   not, so migration-before-deploy ordering matters here, same as any other
   schema-per-tenant change per `database-architecture.md` §5.
4. **Rollback**: each migration's `downgrade()` reverses the add/backfill
   (drop new columns, re-add `is_active` backfilled from the tri-state value
   where applicable). Department's `branch_id` addition is the only
   non-trivial rollback — downgrading drops `branch_id` and restores
   `floor_id` as non-nullable, which is safe only if no department created
   after the upgrade has a null `floor_id`; the downgrade script checks for
   this and refuses to run if any exist, surfacing them for manual handling
   first.

## Open Questions

- Exact wording/values for `SecurityGate.auth_method` (the design shows
  "Biometric/RFID Card", "LPR/PIN Override", "Retina+SmartCard", "No
  Authentication Required" as compound strings) — treat as a free-form
  string for now rather than guessing at an enum split; can be tightened to
  an enum in a later change once the admin team confirms the exact
  selectable list.
