"""form builder: steps, fields, and published config versions

Revision ID: afb2544db111
Revises: 6f3a1c9d4e7b
Create Date: 2026-09-15 00:00:00.000000

Adds `form_steps`/`form_fields` (the admin's mutable draft, branch-scoped
via a nullable `branch_id` — `NULL` is the tenant-wide default scope) and
`form_config_versions` (the immutable-until-next-publish snapshot per
scope, overwritten in place on every publish — no version history in this
iteration, see `openspec/changes/form-builder/design.md` Decision 1).

Every statement here targets a table this same migration creates, so the
connection's `schema_translate_map` alone resolves it correctly — no
`op.add_column`/`op.create_foreign_key` against a pre-existing table (see
275bc2310f49's docstring for why those specifically need an explicit
`schema=`).

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "afb2544db111"
down_revision: str | None = "6f3a1c9d4e7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_form_steps_branch_id"), "form_steps", ["branch_id"], unique=False)
    op.create_index(
        "uq_form_step_branch_key",
        "form_steps",
        ["branch_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND branch_id IS NOT NULL"),
    )
    op.create_index(
        "uq_form_step_default_key",
        "form_steps",
        ["key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND branch_id IS NULL"),
    )

    op.create_table(
        "form_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("placeholder", sa.String(length=255), nullable=True),
        sa.Column("help_text", sa.String(length=500), nullable=True),
        sa.Column("field_type", sa.String(length=30), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("visibility_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("width", sa.String(length=10), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["step_id"], ["form_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_form_fields_step_id"), "form_fields", ["step_id"], unique=False)
    op.create_index(
        "uq_form_field_step_key",
        "form_fields",
        ["step_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "form_config_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_form_config_versions_branch_id"),
        "form_config_versions",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        "uq_form_config_version_branch",
        "form_config_versions",
        ["branch_id"],
        unique=True,
        postgresql_where=sa.text("branch_id IS NOT NULL"),
    )
    op.create_index(
        "uq_form_config_version_default",
        "form_config_versions",
        [sa.text("(branch_id IS NULL)")],
        unique=True,
        postgresql_where=sa.text("branch_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_form_config_version_default", table_name="form_config_versions")
    op.drop_index("uq_form_config_version_branch", table_name="form_config_versions")
    op.drop_index(op.f("ix_form_config_versions_branch_id"), table_name="form_config_versions")
    op.drop_table("form_config_versions")

    op.drop_index("uq_form_field_step_key", table_name="form_fields")
    op.drop_index(op.f("ix_form_fields_step_id"), table_name="form_fields")
    op.drop_table("form_fields")

    op.drop_index("uq_form_step_default_key", table_name="form_steps")
    op.drop_index("uq_form_step_branch_key", table_name="form_steps")
    op.drop_index(op.f("ix_form_steps_branch_id"), table_name="form_steps")
    op.drop_table("form_steps")
