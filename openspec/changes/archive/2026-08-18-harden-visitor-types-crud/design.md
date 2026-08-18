## Context

See `proposal.md` - Why for the full audit table and the verified
reproduction. This is the same defect class as
`archive/2026-08-18-harden-org-structure-crud` — that change's design.md
Decisions 1 and 2 apply here verbatim, just against `visitors`' three
affected constraints instead of `org_structure`'s seven. This document
covers what's specific to `visitors`: the exact constraints, and the
additional form-schema validation gap.

**Affected constraints** (both in
`alembic_tenant/versions/eb8de64c3468_visitor_categories_and_approval_.py`,
confirmed via `\d` against the real `vmss_test` database):

| Table | Constraint | Columns |
|---|---|---|
| `visitor_categories` | `visitor_categories_name_key` | `name` |
| `visitor_categories` | `ix_visitor_categories_code` (unique index) | `code` |
| `approval_workflow_rules` | `uq_workflow_rule_category_step` | `visitor_category_id, step_order` |

## Goals / Non-Goals

**Goals:**
- Make a soft-deleted category's name/code, and a soft-deleted rule's
  step-order slot, actually reusable — matching what the existing app-level
  uniqueness checks already assume, and matching the fix already applied to
  the identical pattern in `org_structure`.
- Close the residual check-then-insert race the same way
  `org_structure`/`auth` already do.
- Reject a `select`-type form field with no options, since it's a
  well-formed-looking but functionally broken config no downstream form
  renderer could actually use.

**Non-Goals:**
- Building the `approvals` rule-evaluation engine — unrelated to these
  defects, already a documented future feature.
- Adding cross-field validation between `escalationMinutes` and
  `autoApproveMinutes` (e.g. requiring auto-approve to fire later than
  escalation). Nothing in API-06's requirement or this feature's own design
  notes asks for that relationship to be enforced; flagging a `select` field
  with no options is a narrower, clearly-broken-config case, not a general
  invitation to add speculative cross-field rules.

## Decisions

### Decision 1: Partial unique indexes scoped to `deleted_at IS NULL` (mirrors org_structure Decision 1)

Replace `VisitorCategory.name`/`.code`'s column-level `unique=True` and
`ApprovalWorkflowRule`'s `UniqueConstraint("visitor_category_id",
"step_order")` with `Index(..., unique=True, postgresql_where=text("deleted_at
IS NULL"))` in `__table_args__`, and a matching `alembic_tenant` migration
that drops the old constraint/index and creates the new partial one.

**Alternative considered**: same two alternatives design.md Decision 1
considered in `harden-org-structure-crud` (drop DB-level uniqueness
entirely; make delete hard instead of soft) — rejected for the same
reasons: dropping the DB constraint reopens a TOCTOU race, and hard-deleting
a visitor category or approval rule would break any future report/audit
trail referencing it by id even after it's retired.

### Decision 2: Catch `IntegrityError` at the service layer as defense-in-depth (mirrors org_structure Decision 2)

Wrap `create_visitor_category`/`update_visitor_category`,
`create_approval_workflow_rule`/`update_approval_workflow_rule`'s
`commit()` calls in the same `_commit_or_conflict`-style helper introduced
in `org_structure/service.py` — reusing the identical pattern (a
`visitors`-local helper, not a shared cross-feature import, matching this
codebase's existing posture of not sharing service-layer helpers across
feature packages).

**Alternative considered**: extract `_commit_or_conflict` into `core/` so
every feature reuses one implementation. Rejected as scope creep for this
change — three feature packages each having their own trivial ~8-line
helper is cheaper than introducing a new shared `core` utility and updating
every existing call site to import it, for a change already scoped to a
compliance fix, not a refactor. Worth revisiting if a fourth feature needs
the same pattern.

### Decision 3: Reject a `select` field with no options

Add a `model_validator` (or `field_validator` combination) to
`FormFieldDefinition` that raises when `field_type == FormFieldType.select`
and `options` is `None` or empty.

**Alternative considered**: also require non-empty `options` for
`checkbox`. Rejected — `checkbox` here represents a single boolean toggle
(per the PDF requirement's own visitor-registration examples and this
schema's `required: bool` sibling field), not a multi-select checkbox
group, so an empty/absent `options` on a checkbox field is the normal case,
not a defect.

## Risks / Trade-offs

- [Risk]/[Trade-off]: identical to `harden-org-structure-crud`'s design.md
  (narrower partial index can't fail against data that passed the old
  constraint; brief two-index window during migration `upgrade()`).

## Migration Plan

- New `alembic_tenant` revision, `Revises: 880cf061a484` (the head left by
  `harden-org-structure-crud`): for `visitor_categories.name`,
  `visitor_categories.code`, and
  `approval_workflow_rules(visitor_category_id, step_order)`, drop the
  existing unconditional constraint/index and create a unique index scoped
  to `deleted_at IS NULL` in its place. `downgrade()` reverses both steps
  per table.
- Same apply path as every other tenant migration
  (`database-architecture.md` §5). No data backfill needed.
- No `.env`/`settings` changes. No new dependencies.
