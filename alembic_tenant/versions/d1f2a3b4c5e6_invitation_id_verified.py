"""invitation_id_verified: reception ID-check confirmation columns

Revision ID: d1f2a3b4c5e6
Revises: c4a8e1f7d093
Create Date: 2026-11-02 00:00:00.000000

add-badge-print-flow: nullable `id_verified_at`/`id_verified_by_user_id` on
`invitations`. Additive and nullable, so safe to apply before the code ships.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1f2a3b4c5e6"
down_revision: str | Sequence[str] | None = "c4a8e1f7d093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    # `add_column`/FK ops don't go through `schema_translate_map` (unlike
    # `create_table`), so the target schema is explicit — same as `bc9c5b3c20b6`.
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column("id_verified_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column("id_verified_by_user_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_id_verified_by_user_id_users",
        "invitations",
        "users",
        ["id_verified_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_constraint(
        "fk_invitations_id_verified_by_user_id_users",
        "invitations",
        type_="foreignkey",
        schema=schema,
    )
    op.drop_column("invitations", "id_verified_by_user_id", schema=schema)
    op.drop_column("invitations", "id_verified_at", schema=schema)
