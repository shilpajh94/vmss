"""invitations: lifecycle-action columns (deny/check-in/check-out/badge/watchlist-override)

Revision ID: 787f2f641092
Revises: 4bcbb42bc353
Create Date: 2026-08-31 00:00:00.000000

`add-invitation-lifecycle-actions/design.md` Decision 1: one migration for
every new `invitations` column the 8 new lifecycle endpoints need. Every
column is nullable (or defaulted for `badge_reprint_count`/
`watchlist_flagged`), so every existing row backfills cleanly with no
separate data migration — no existing column's meaning changes.

Every `op.add_column` below passes `schema=_target_schema()` explicitly —
`op.add_column` does not pick up the connection's `schema_translate_map`
the way `op.create_table` does (same verified gotcha `c3d8f21a9b6e`'s
docstring documents), so without it these would land on whatever schema is
first on the connection's plain `search_path` instead of the target tenant
schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "787f2f641092"
down_revision: str | None = "4bcbb42bc353"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _new_columns() -> list[sa.Column]:
    """A fresh `Column` instance per call — `op.add_column` attaches each
    column to a synthetic table internally, so a shared module-level
    instance can't be passed to it twice (e.g. across upgrade/downgrade/
    upgrade in the same process, as the test suite's migration round-trip
    does) without hitting SQLAlchemy's "Column object already assigned"
    error, and its own `Column.copy()` escape hatch is deprecated.
    """
    return [
        sa.Column("denial_reason", sa.String(length=500), nullable=True),
        sa.Column("denied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_out_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("badge_number", sa.String(length=20), nullable=True),
        sa.Column("badge_storage_key", sa.String(length=500), nullable=True),
        sa.Column("badge_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("badge_reprint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("watchlist_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("watchlist_override_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watchlist_override_reason", sa.String(length=500), nullable=True),
        sa.Column("watchlist_override_by_user_id", sa.Uuid(), nullable=True),
    ]


_NEW_COLUMN_NAMES: list[str] = [c.name for c in _new_columns() if c.name is not None]


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    for column in _new_columns():
        op.add_column("invitations", column, schema=schema)
    op.create_index(
        "ix_invitations_badge_number",
        "invitations",
        ["badge_number"],
        unique=True,
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_checked_in_by_user_id_users",
        "invitations",
        "users",
        ["checked_in_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_checked_out_by_user_id_users",
        "invitations",
        "users",
        ["checked_out_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_watchlist_override_by_user_id_users",
        "invitations",
        "users",
        ["watchlist_override_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_constraint(
        "fk_invitations_watchlist_override_by_user_id_users",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_invitations_checked_out_by_user_id_users",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_invitations_checked_in_by_user_id_users",
        "invitations",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_index("ix_invitations_badge_number", table_name="invitations", schema=schema)
    for name in reversed(_NEW_COLUMN_NAMES):
        op.drop_column("invitations", name, schema=schema)
