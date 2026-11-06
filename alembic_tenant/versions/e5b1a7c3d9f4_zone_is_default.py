"""zone_is_default: one default zone per branch

Revision ID: e5b1a7c3d9f4
Revises: d3a7c9e1b5f2
Create Date: 2026-11-06 00:00:00.000000

add-default-zone-for-all-visitors: `zones.is_default` marks the zone every visitor
of the branch may always enter. The partial unique index makes "one live default
per branch" a database guarantee. No zone is default until an admin sets one.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5b1a7c3d9f4"
down_revision: str | Sequence[str] | None = "d3a7c9e1b5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str:
    # Tenant migrations are applied per schema; DDL helpers aren't covered by
    # schema_translate_map, so qualify explicitly (see d3a7c9e1b5f2).
    return op.get_context().version_table_schema or ""


def upgrade() -> None:
    schema = _schema()
    op.add_column(
        "zones",
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema=schema,
    )
    op.create_index(
        "uq_zone_branch_default",
        "zones",
        ["branch_id"],
        unique=True,
        schema=schema,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_index("uq_zone_branch_default", table_name="zones", schema=schema)
    op.drop_column("zones", "is_default", schema=schema)
