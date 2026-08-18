"""visitor types: scope unique name/code/step constraints to non-deleted rows

Revision ID: 2b57bd4b7d9d
Revises: 880cf061a484
Create Date: 2026-08-18 00:00:00.000000

Same defect and fix as `880cf061a484` (org_structure), applied to
`visitors`: `visitor_categories.name`, `visitor_categories.code`, and
`approval_workflow_rules(visitor_category_id, step_order)` were each backed
by an unconditional unique constraint/index, even though their create
paths' `get_by_name`/`get_by_code`/`get_by_category_and_step` pre-checks
(`repository.py`) already filter `deleted_at IS NULL` before deciding a
value is free. Verified directly against Postgres (see
openspec/changes/harden-visitor-types-crud/proposal.md) that this let a
soft-deleted category's code block the very next attempt to reuse it,
failing with an unhandled `IntegrityError` instead of the friendly 409 the
pre-check was clearly written to produce.

Strictly narrows what's enforced (nothing currently reuses a soft-deleted
row's name/code/step), so no existing data can violate the new indexes.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` limitation as every migration in this tree (see
275bc2310f49's docstring).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b57bd4b7d9d"
down_revision: str | None = "880cf061a484"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOT_DELETED = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.drop_constraint("visitor_categories_name_key", "visitor_categories", type_="unique")
    op.create_index(
        "visitor_categories_name_key",
        "visitor_categories",
        ["name"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_index(op.f("ix_visitor_categories_code"), table_name="visitor_categories")
    op.create_index(
        op.f("ix_visitor_categories_code"),
        "visitor_categories",
        ["code"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint(
        "uq_workflow_rule_category_step", "approval_workflow_rules", type_="unique"
    )
    op.create_index(
        "uq_workflow_rule_category_step",
        "approval_workflow_rules",
        ["visitor_category_id", "step_order"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )


def downgrade() -> None:
    op.drop_index("uq_workflow_rule_category_step", table_name="approval_workflow_rules")
    op.create_unique_constraint(
        "uq_workflow_rule_category_step",
        "approval_workflow_rules",
        ["visitor_category_id", "step_order"],
    )

    op.drop_index(op.f("ix_visitor_categories_code"), table_name="visitor_categories")
    op.create_index(
        op.f("ix_visitor_categories_code"), "visitor_categories", ["code"], unique=True
    )

    op.drop_index("visitor_categories_name_key", table_name="visitor_categories")
    op.create_unique_constraint(
        "visitor_categories_name_key", "visitor_categories", ["name"]
    )
