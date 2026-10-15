"""invitations approval revert columns

Revision ID: bc9c5b3c20b6
Revises: bff38dfa42e7
Create Date: 2026-10-13 00:00:00.000000

`add-invitation-approval-revert` adds `PATCH /invitations/{id}/revert-
approval`, which records the latest revert on three new nullable
`invitations` columns (design.md Decision 1). The matching permission grant
is the next revision, `6054f5200ed1`.

New columns on a pre-existing table, so `op.add_column`/`op.drop_column`
pass `schema=` explicitly, and the FK is created with explicit
`source_schema`/`referent_schema` (same as `787f2f641092`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc9c5b3c20b6"
down_revision: str | Sequence[str] | None = "bff38dfa42e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "fk_invitations_approval_reverted_by_user_id_users"


def _new_columns() -> list[sa.Column]:
    """Fresh `Column` instances per call — see `787f2f641092._new_columns`."""
    return [
        sa.Column("approval_reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_reverted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approval_revert_reason", sa.String(length=500), nullable=True),
    ]


_NEW_COLUMN_NAMES: list[str] = [c.name for c in _new_columns() if c.name is not None]


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    for column in _new_columns():
        op.add_column("invitations", column, schema=schema)
    op.create_foreign_key(
        _FK_NAME,
        "invitations",
        "users",
        ["approval_reverted_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_constraint(_FK_NAME, "invitations", schema=schema, type_="foreignkey")
    for name in reversed(_NEW_COLUMN_NAMES):
        op.drop_column("invitations", name, schema=schema)
