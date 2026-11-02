"""badge_prints: append-only badge print/reprint log

Revision ID: e2a3b4c5d6f7
Revises: d1f2a3b4c5e6
Create Date: 2026-11-02 00:00:00.000000

add-badge-print-flow. One row per print or reprint; the only permitted update
is `active` true -> false. The partial unique index guarantees at most one
active badge per visit, so concurrent double-prints fail cleanly.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2a3b4c5d6f7"
down_revision: str | Sequence[str] | None = "d1f2a3b4c5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "badge_prints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("printed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("reprint_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["visit_id"], ["invitations.id"]),
        sa.ForeignKeyConstraint(["printed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_badge_prints_jti"),
    )
    # Index ops don't go through `schema_translate_map` (unlike `create_table`).
    schema = op.get_context().version_table_schema
    op.create_index("ix_badge_prints_visit_id", "badge_prints", ["visit_id"], schema=schema)
    op.create_index(
        "uq_badge_prints_one_active_per_visit",
        "badge_prints",
        ["visit_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        schema=schema,
    )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_index("uq_badge_prints_one_active_per_visit", table_name="badge_prints", schema=schema)
    op.drop_index("ix_badge_prints_visit_id", table_name="badge_prints", schema=schema)
    op.drop_table("badge_prints", schema=schema)
