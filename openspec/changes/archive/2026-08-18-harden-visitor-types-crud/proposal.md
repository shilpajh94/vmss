## Why

The user asked to verify the already-delivered Visitor Types implementation
against:

> API-05 · Visitor Types · CRUD: Visitor Category with configurable form
> schema per category
>
> API-06 · Visitor Types · CRUD: Approval workflow rules per visitor category

with proper test-case validation, not just a code read.

Full CRUD exists for both `VisitorCategory` (with a validated, JSONB-backed
configurable form schema) and `ApprovalWorkflowRule` (an ordered,
per-category approval chain referencing `auth.Role`), each with
`response_model`-documented endpoints, permission checks, audit logging, and
21 passing tests covering happy paths, permission-denial, and
tenant-schema isolation. Re-checking it against the exact same class of
defect this session already found and fixed once in `org_structure`
(`archive/2026-08-18-harden-org-structure-crud`) surfaced the identical
pattern here, unfixed, plus one small form-schema validation gap.

**Audit result:**

| API | Requirement | Verdict |
|---|---|---|
| API-05 | Visitor Category CRUD | **Compliant**, with the defect below |
| API-05 | Configurable form schema per category | **Compliant**, with the minor gap below |
| API-06 | Approval workflow rules CRUD per category | **Compliant**, with the defect below |
| API-06 | Rule ordering (`stepOrder`), mandatory/optional, escalation/auto-approve timers | **Compliant** — configuration only, by design; actual rule *evaluation* against a live visit is the not-yet-built `approvals` feature, already flagged as a deliberate non-goal in this feature's own docstrings, not a hidden gap |
| Cross-cutting | Soft-delete then reuse the same name/code/step | **Defect** — reproduced directly against Postgres, the identical defect class fixed in `org_structure` last session: `VisitorCategory.name`, `VisitorCategory.code`, and `ApprovalWorkflowRule(visitor_category_id, step_order)` are all backed by unconditional unique constraints, while the app-level `get_by_name`/`get_by_code`/`get_by_category_and_step` pre-checks (`repository.py`) already filter `deleted_at IS NULL` before deciding a value is free. A soft-deleted category's `code` stays reserved forever at the DB level and the next attempt to reuse it raises an unhandled `IntegrityError` (bare 500) instead of the 409 the pre-check was clearly written to produce. |
| Cross-cutting | Form field validation completeness | **Minor gap** — a `select`-type form field can be saved with `options: null` or an empty list, which is nonsensical (nothing to select from) and would break whatever form renders it once `invitations`/`checkin` are built; `security-architecture.md` §4 calls for real constraints, not just type-checking, and this is the one field-shape rule the schema doesn't enforce. |

**How the defect was verified**: in a rolled-back transaction against the
real `vmss_test` database (`tenant_acme_test` schema), a `VisitorCategory`
row was inserted, soft-deleted, confirmed absent from the app-level
"is this code taken?" query (0 rows), and a second insert with the same
`code` was attempted — Postgres raised
`duplicate key value violates unique constraint "ix_visitor_categories_code"`.
The migration that created these tables
(`alembic_tenant/versions/eb8de64c3468_visitor_categories_and_approval_.py`)
defines `visitor_categories.name`/`.code` and
`approval_workflow_rules(visitor_category_id, step_order)` as plain,
unconditional constraints/indexes — none scoped to `deleted_at IS NULL` —
confirmed against the live schema via `\d`.

## What Changes

- Convert the unconditional unique constraints on `VisitorCategory.name`,
  `VisitorCategory.code`, and
  `ApprovalWorkflowRule(visitor_category_id, step_order)` into **partial
  unique indexes** scoped to `deleted_at IS NULL`, via a new
  `alembic_tenant` migration (revises `880cf061a484`, the head left by
  `harden-org-structure-crud`) — mirroring that same change's fix exactly.
- Add an `IntegrityError` → 409 catch around every `visitors` create/update
  path that writes one of these columns, as defense-in-depth against the
  residual check-then-insert race — same `_commit_or_conflict` pattern
  already proven in `org_structure/service.py` and
  `auth/service.py::sync_employee_directory`.
- Add a `FormFieldDefinition` validator rejecting a `select`-type field with
  no (or empty) `options`.
- Add regression tests: soft-delete-then-recreate-with-the-same-name/code/
  step succeeds, for `VisitorCategory` (name and code, separately) and
  `ApprovalWorkflowRule` (step order); a `select` field with no options is
  rejected with 422.
- **Non-goal, explicitly deferred**: building the `approvals` rule-evaluation
  engine (API-06's actual runtime behavior once a visit exists) — already an
  explicit, documented non-goal of this feature, unrelated to the defects
  found here.

## Capabilities

### New Capabilities
- `visitors`: baseline requirements for the `VisitorCategory`/
  `ApprovalWorkflowRule` CRUD and configurable form schema — the `visitors`
  feature package has never had a baseline spec captured under
  `openspec/specs/`, so this change establishes it (same reasoning as the
  `auth` and `org-structure` baselines established in this session's prior
  two archived changes).

### Modified Capabilities
- None.

## Impact

- **Code**: `src/vmss_api/visitors/models.py` (unique constraints → partial
  unique indexes), `src/vmss_api/visitors/service.py` (`IntegrityError` →
  409 on the affected create/update calls), `src/vmss_api/visitors/schemas.py`
  (`FormFieldDefinition` select-options validator), a new file under
  `alembic_tenant/versions/`.
- **Tests**: 4 new soft-delete-then-recreate cases plus 1 new
  select-without-options validation case in `visitors/tests.py`.
- **Migration**: existing tenant schemas need the new `alembic_tenant`
  revision applied, same as `harden-org-structure-crud`'s.
- **No breaking changes**: the partial index accepts every row the old
  constraint did and additionally accepts a case that previously 500'd; the
  select-options validator only rejects a shape nothing currently exercises
  (no existing test or seed data creates a `select` field with empty
  options).
- **Out of scope**: the `approvals` rule-evaluation engine.
