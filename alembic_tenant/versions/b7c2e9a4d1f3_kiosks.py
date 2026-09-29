"""kiosks: admin-managed kiosk records

Revision ID: b7c2e9a4d1f3
Revises: 24b02534e970, a1b2c3d4e5f6
Create Date: 2026-09-29 00:00:00.000000

Also merges the two pre-existing tenant heads (see
`fix-tenant-migration-branch-drift`). `op.create_table`/`op.create_index`
honor the connection's `schema_translate_map`, so no explicit `schema=`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c2e9a4d1f3"
down_revision: str | Sequence[str] | None = ("24b02534e970", "a1b2c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kiosks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
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
    )
    op.create_index(op.f("ix_kiosks_is_hidden"), "kiosks", ["is_hidden"], unique=False)
    op.create_index(
        "ix_kiosks_name_lower",
        "kiosks",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_kiosks_name_lower", table_name="kiosks")
    op.drop_index(op.f("ix_kiosks_is_hidden"), table_name="kiosks")
    op.drop_table("kiosks")
