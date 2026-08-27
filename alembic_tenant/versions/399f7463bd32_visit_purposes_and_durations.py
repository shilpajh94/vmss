"""visit_info: visit_purposes and visit_durations catalogs

Revision ID: 399f7463bd32
Revises: 39c3f5112585
Create Date: 2026-08-24 00:00:00.000000

Backs `GET /visit-info/options` (visit-info-lookup-api): real, seeded
purpose/duration lists in place of the app's previously hardcoded ones. See
openspec/changes/visit-info-lookup-api/design.md.

`op.create_table` resolves against the connection's `schema_translate_map`
without an explicit `schema=` kwarg — unlike `op.add_column`/`op.alter_column`
(see the next migration in this chain, and
c3d8f21a9b6e's docstring for the verified gotcha).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "399f7463bd32"
down_revision: str | None = "39c3f5112585"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit_purposes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "visit_durations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("visit_durations")
    op.drop_table("visit_purposes")
