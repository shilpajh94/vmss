## Context

See `proposal.md` - Why for the audit table and the verified reproduction.
This document covers the fix mechanics for the one defect found (an
unconditional unique constraint outliving a soft delete) across all seven
affected entities, plus the small `Company.email` validation fix.

**Why every entity hit the same bug.** `database-architecture.md` §4 commits
this codebase to soft delete (`deleted_at`, filtered out by default) for
anything with compliance/audit relevance — which every `org_structure`
entity has (it's the org chart a visitor's check-in/access grant will
eventually reference). Every entity's create path already has a
`get_by_code`/`get_by_number` guard that filters `deleted_at IS NULL` before
deciding whether a code is taken — clear evidence the intent was always "a
deleted row's code becomes reusable." But the actual Postgres constraint
backing that guard is a plain, unconditional `UniqueConstraint` (or, for
`Branch.code`, a plain unique index from `mapped_column(unique=True)`) —
scoped to the whole table, deleted rows included. The app-level guard and
the DB-level constraint disagree, and the DB always wins: the guard says
"free," the `INSERT` says "taken." Verified directly against Postgres (see
proposal.md) rather than inferred from reading the migration alone.

**Affected constraints** (all in
`alembic_tenant/versions/275bc2310f49_*.py` /
`8f3b6a19d5e2_*.py`, confirmed via `\d` against the real `vmss_test`
database):

| Table | Constraint | Columns |
|---|---|---|
| `branches` | `ix_branches_code` (unique index) | `code` |
| `companies` | `companies_registration_number_key` | `registration_number` |
| `buildings` | `uq_building_branch_code` | `branch_id, code` |
| `floors` | `uq_floor_building_number` | `building_id, floor_number` |
| `departments` | `uq_department_floor_code` | `floor_id, code` |
| `reception_desks` | `uq_desk_floor_code` | `floor_id, code` |
| `security_gates` | `uq_gate_branch_code` | `branch_id, code` |

## Goals / Non-Goals

**Goals:**
- Make a soft-deleted entity's code/number actually reusable, matching what
  the existing app-level uniqueness checks already assume.
- Close the residual check-then-insert race with a clean 409 instead of an
  unhandled 500, using the same `IntegrityError` catch pattern already
  proven in `auth/service.py::sync_employee_directory`.
- Fix `Company.email`'s validation gap to match the rest of the codebase.

**Non-Goals:**
- Auditing every other soft-deletable model in the codebase for the same
  pattern (e.g. `auth.User.email`, `Role.name`). `User` rows are never
  soft-deleted by any current code path (`sync_employee_directory`
  deactivates, doesn't delete), so that risk isn't live today — flagged in
  proposal.md as a note for whoever adds the next soft-delete-eligible
  unique column, not fixed speculatively here.
- Changing soft-delete semantics generally, or adding a "purge" job for old
  soft-deleted rows. Out of scope — this only fixes the constraint's scope
  to match the *existing* semantics.

## Decisions

### Decision 1: Partial unique indexes scoped to `deleted_at IS NULL`, not application-only dedup

Replace each affected `UniqueConstraint`/unique column with a plain SQLAlchemy
`Index(..., unique=True, postgresql_where=sa.text("deleted_at IS NULL"))` in
`__table_args__`, and a matching `alembic_tenant` migration that drops the
old constraint/index and creates the new partial one under the same
(or a clearly related) name.

**Alternative considered**: drop the DB-level uniqueness entirely and rely
only on the app-level `get_by_code` check before insert. Rejected — that
reopens exactly the race a concurrent-safe system needs a DB constraint for;
an app-level check-then-insert with no backing constraint is a textbook
TOCTOU bug under concurrent requests, which this project's own
`api-conventions.md` §3 (idempotency for mutating endpoints) already treats
as a real, not theoretical, concern for this codebase.

**Alternative considered**: keep the constraint unconditional and instead
make delete *hard* (actually remove the row) for these entities so no
soft-deleted row lingers to collide. Rejected — `database-architecture.md`
§4 requires soft delete for anything with compliance/audit relevance, and
every entity here (branch, building, floor, department, desk, gate) is
exactly that; losing the historical row would break any future report that
joins through it (e.g. "which department did this check-in happen in,"
even after the department was deactivated).

### Decision 2: Catch `IntegrityError` at the service layer as defense-in-depth, not a replacement for the app-level check

Keep every existing `get_by_code`/`get_by_number` pre-check (it's the fast
path and gives a friendly, specific 409 message before touching the
database for the common case), and additionally wrap the `commit()` in a
`try/except IntegrityError` that rolls back and raises the same 409 — for
the residual window where two concurrent requests both pass the pre-check
before either commits. Mirrors
`auth/service.py::sync_employee_directory`'s existing
`IntegrityError` → 409 handling for the identical reason (see its
`try: await tenant_db.commit() / except IntegrityError` block).

**Alternative considered**: rely on the partial unique index alone and let
a genuine race surface as an unhandled 500. Rejected — `security-architecture.md`
§4's exception-handling rule (no stack traces/raw DB errors reaching the
client) already forbids this outcome; a 409 on the rare race is strictly
better and costs one `try/except` per affected call.

### Decision 3: `Company.email` becomes `EmailStr`

Change `CompanyCreate.email`/`CompanyUpdate.email` from `str` to `EmailStr`
in `org_structure/schemas.py`, matching `auth`/`platform`/`invitations`.

**Alternative considered**: leave it as `str` since `Company.email` is a
business contact address, not a login credential, and its format doesn't
gate access to anything. Rejected — `security-architecture.md` §4 doesn't
carve out an exception for "non-login" emails, and a malformed contact email
silently accepted here would surface downstream wherever this field is used
in an actual notification (e.g. `notifications`, once built) as a delivery
failure with no useful validation error at the point of entry.

## Risks / Trade-offs

- [Risk] Applying the new migration to an already-provisioned tenant schema
  requires that schema currently have zero constraint violations under the
  *new*, narrower partial index (i.e., no two non-deleted rows already
  sharing a code) — otherwise the migration itself fails to apply.
  → Mitigation: the new partial index is strictly narrower in scope than the
  old unconditional one (it only ever excludes rows the old index also
  covered), so anything that satisfied the old constraint still satisfies
  the new one; there's no way for this migration to fail against data that
  passed the old constraint.
- [Trade-off] Two similarly-named indexes exist momentarily during the
  migration's `upgrade()` (drop-then-create, not a single atomic rename) →
  accepted; this is a schema change applied during a maintenance/deploy
  window per `database-architecture.md` §5, not a hot data migration under
  live traffic.

## Migration Plan

- New `alembic_tenant` revision: for each of the seven tables, `DROP
  CONSTRAINT`/`DROP INDEX` the old unconditional uniqueness, then
  `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`. Downgrade reverses
  both steps per table.
- Applied the same way every other tenant migration is — once per tenant
  schema, via `platform/service.py`'s provisioning/upgrade path
  (`database-architecture.md` §5) — no data backfill needed, since the new
  index only narrows what's already enforced.
- No `.env`/`settings` changes. No new dependencies.
