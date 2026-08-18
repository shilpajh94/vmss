"""visitor categories and approval workflow rules

Revision ID: eb8de64c3468
Revises: 275bc2310f49
Create Date: 2026-08-17 00:00:00.000000

Adds `visitor_categories` (a configurable visitor type with a JSONB
`form_schema` — API-05) and `approval_workflow_rules` (an ordered per-category
approval chain, referencing `roles` — API-06). Both are tenant-scoped, plain
config tables: no branch scoping, same posture as `companies`/`branches`
themselves (docs/features/org_structure.md).

Hand-written, not `alembic revision --autogenerate` — see 275bc2310f49's
docstring for why every migration in this tree is (the `include_schemas=True`
cross-schema-FK limitation applies here too, even though this migration adds
no new cross-schema FK itself).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eb8de64c3468"
down_revision: str | None = "275bc2310f49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visitor_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("form_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_visitor_categories_code"), "visitor_categories", ["code"], unique=True)

    op.create_table(
        "approval_workflow_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("visitor_category_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_role_id", sa.Uuid(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("escalation_minutes", sa.Integer(), nullable=True),
        sa.Column("auto_approve_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["visitor_category_id"], ["visitor_categories.id"]),
        sa.ForeignKeyConstraint(["approver_role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "visitor_category_id", "step_order", name="uq_workflow_rule_category_step"
        ),
    )
    op.create_index(
        op.f("ix_approval_workflow_rules_visitor_category_id"),
        "approval_workflow_rules",
        ["visitor_category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflow_rules_approver_role_id"),
        "approval_workflow_rules",
        ["approver_role_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_approval_workflow_rules_approver_role_id"), table_name="approval_workflow_rules"
    )
    op.drop_index(
        op.f("ix_approval_workflow_rules_visitor_category_id"),
        table_name="approval_workflow_rules",
    )
    op.drop_table("approval_workflow_rules")

    op.drop_index(op.f("ix_visitor_categories_code"), table_name="visitor_categories")
    op.drop_table("visitor_categories")
