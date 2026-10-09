"""invitations.building_id

Revision ID: d4e9a2b7c1f6
Revises: c3d8f1a6b2e4
Create Date: 2026-09-30 00:00:00.000000

Column on a pre-existing table, so `schema=` is passed explicitly (see
`c3d8f1a6b2e4`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9a2b7c1f6"
down_revision: str | Sequence[str] | None = "c3d8f1a6b2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column("building_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_building_id",
        "invitations",
        "buildings",
        ["building_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        "ix_invitations_building_id", "invitations", ["building_id"], schema=schema
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_index("ix_invitations_building_id", table_name="invitations", schema=schema)
    op.drop_constraint("fk_invitations_building_id", "invitations", schema=schema, type_="foreignkey")
    op.drop_column("invitations", "building_id", schema=schema)
