## Why

The user asked to verify the already-delivered Org Setup implementation
against:

> API-03 · Org Setup · CRUD: Company, Branch/Location, Building, Floor,
> Department (single company, multiple branches)
>
> API-04 · Org Setup · CRUD: Reception Desk, Security Gate, Employee
> directory sync

with the instruction to judge it against sound requirement intent and
FastAPI/coding-standard practice, not a literal checklist match.

Full CRUD exists for all seven entities (`org_structure/router.py`,
`service.py`, `repository.py`) plus the employee-directory sync endpoint
(`auth/router.py`), backed by 70 + 6 passing tests covering happy paths,
permission-denial, tenant-schema isolation, and cross-branch 404s for every
entity — this is genuinely solid, well-layered work. Re-reading it against
this project's own `database-architecture.md` §4 ("soft delete... filtered
out by default in repository queries") surfaced one real, reproducible
defect common to every entity, plus one small input-validation
inconsistency.

**Audit result:**

| API | Requirement | Verdict |
|---|---|---|
| API-03 | Company CRUD, singleton enforced | **Compliant**, with the defect below |
| API-03 | Branch CRUD (single company, multiple branches) | **Compliant**, with the defect below |
| API-03 | Building/Floor/Department CRUD, branch-scoped | **Compliant**, with the defect below |
| API-04 | Reception Desk / Security Gate CRUD, branch-scoped | **Compliant**, with the defect below |
| API-04 | Employee directory sync | **Compliant** — batch reconcile, department validation, N+1-safe bulk queries (`query-performance.md` §2/§3), deactivation instead of deletion |
| Cross-cutting | Soft-delete then reuse the same code/number | **Defect** — reproduced directly against Postgres: a soft-deleted `Branch`/`Company`/`Building`/`Floor`/`Department`/`ReceptionDesk`/`SecurityGate` row's unique code/number stays reserved at the DB level forever, even though the app-level `get_by_code`/`get_by_number` checks (which filter `deleted_at IS NULL`) report it as free. The very next `INSERT` a client would naturally trigger raises an unhandled `IntegrityError`, surfacing as a bare 500 instead of the friendly 409 the existing app-level check was clearly written to produce. |
| Cross-cutting | Input validation on `Company.email` | **Minor gap** — plain `str`, not `EmailStr`. Every other feature's email field (`auth`, `platform`, `invitations`) uses `EmailStr`; `Company`'s doesn't, an inconsistency with `security-architecture.md` §4 ("real constraints... not just str"). |

**How the defect was verified** (not just read from code): in a rolled-back
transaction against the real `vmss_test` database (`tenant_acme_test`
schema), a `Branch` row was inserted, soft-deleted
(`deleted_at = now()`), confirmed absent from the app-level "is this code
taken" query (0 rows), and then a second insert with the *same* `code`
was attempted — Postgres raised
`duplicate key value violates unique constraint "ix_branches_code"`. The
migration that created every one of these constraints
(`alembic_tenant/versions/275bc2310f49_*.py`,
`.../8f3b6a19d5e2_*.py`) defines them as plain, unconditional
`UniqueConstraint`/unique index — none scoped to `deleted_at IS NULL` — so
the same failure mode applies identically to `Company.registration_number`,
`Building(branch_id, code)`, `Floor(building_id, floor_number)`,
`Department(floor_id, code)`, `ReceptionDesk(floor_id, code)`, and
`SecurityGate(branch_id, code)`.

## What Changes

- Convert the unconditional unique constraints on `Branch.code`,
  `Company.registration_number`, `Building(branch_id, code)`,
  `Floor(building_id, floor_number)`, `Department(floor_id, code)`,
  `ReceptionDesk(floor_id, code)`, and `SecurityGate(branch_id, code)` into
  **partial unique indexes** scoped to `deleted_at IS NULL`, via a new
  `alembic_tenant` migration — so a soft-deleted row's code/number is
  actually freed for reuse, matching what the existing app-level
  `get_by_code`/`get_by_number` checks already assume.
- Add an `IntegrityError` → 409 catch around every `org_structure` create/
  update path that writes one of these columns, as defense-in-depth against
  the unavoidable check-then-insert race (two concurrent requests both
  passing the app-level uniqueness check before either commits) — mirroring
  the pattern `auth/service.py::sync_employee_directory` already uses for
  the same reason.
- Change `CompanyCreate.email`/`CompanyUpdate.email` from `str` to
  `EmailStr`, matching every other email field in the codebase.
- Add regression tests: soft-delete-then-recreate-with-the-same-code/number
  succeeds, for `Branch`, `Company` (`registration_number`), `Building`,
  `Floor`, `Department`, `ReceptionDesk`, and `SecurityGate`; malformed
  `Company.email` is rejected with 422.
- **Non-goal, explicitly deferred**: auditing every other soft-deletable
  entity in the codebase (e.g. `auth.User.email`) for the same
  unconditional-unique-constraint pattern. `User` rows aren't currently
  soft-deleted by any existing code path (`sync_employee_directory`
  deactivates, never soft-deletes), so that specific corner isn't reachable
  today — flagging it here as a related risk for whoever builds the next
  feature that does soft-delete a uniquely-constrained row, not bundling a
  speculative fix into this change.

## Capabilities

### New Capabilities
- `org-structure`: baseline requirements for the Company/Branch/Building/
  Floor/Department/ReceptionDesk/SecurityGate hierarchy and its branch-scoped
  access model — the `org_structure` feature package has never had a
  baseline spec captured under `openspec/specs/`, so this change establishes
  it (same reasoning as the `auth` capability baseline established in
  `archive/2026-08-18-close-auth-access-audit-gaps`).

### Modified Capabilities
- None.

## Impact

- **Code**: `src/vmss_api/org_structure/models.py` (unique constraints →
  partial unique indexes), `src/vmss_api/org_structure/service.py`
  (`IntegrityError` → 409 on the affected create/update calls),
  `src/vmss_api/org_structure/schemas.py` (`CompanyCreate`/`CompanyUpdate`
  `email` → `EmailStr`), a new file under `alembic_tenant/versions/`.
- **Tests**: 7 new soft-delete-then-recreate cases plus 1 new email-validation
  case in `org_structure/tests.py`.
- **Migration**: existing tenant schemas need the new `alembic_tenant`
  revision applied (`platform/service.py`'s per-tenant upgrade path — see
  `database-architecture.md` §5); no data migration, only an index swap.
- **No breaking changes**: the partial index accepts every row the old
  constraint did (nothing currently relies on a soft-deleted code staying
  blocked) and additionally accepts a case that previously 500'd; the 409
  guard only fires on the same race window that previously surfaced as a
  raw `IntegrityError`, so callers see a cleaner error, not a new one.
- **Out of scope**: the `User.email` non-partial-unique-index risk noted
  above.
