"""sso_providers.allow_admin_login

Revision ID: c3d8f1a6b2e4
Revises: b7c2e9a4d1f3
Create Date: 2026-09-29 00:00:00.000000

A new column on a pre-existing table, so `op.add_column`/`op.drop_column`
pass `schema=` explicitly — the connection's `schema_translate_map` alone
doesn't resolve it the way `op.create_table` does (see `f1a2c7e9b3d5`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d8f1a6b2e4"
down_revision: str | Sequence[str] | None = "b7c2e9a4d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    op.add_column(
        "sso_providers",
        sa.Column("allow_admin_login", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=_target_schema(),
    )


def downgrade() -> None:
    op.drop_column("sso_providers", "allow_admin_login", schema=_target_schema())
