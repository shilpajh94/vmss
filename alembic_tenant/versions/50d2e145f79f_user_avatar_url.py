"""auth: user avatar url

Revision ID: 50d2e145f79f
Revises: 524da546af26
Create Date: 2026-08-19 00:00:03.000000

The admin employee directory design shows an avatar/profile photo per
employee, which `users` had no field for. Purely additive — no backfill.

Passes `schema=` explicitly on `add_column` (275bc2310f49's landmine —
`op.add_column` does not honor `schema_translate_map` on an existing table
the way `op.create_table` does).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50d2e145f79f"
down_revision: str | None = "524da546af26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True), schema=schema)


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("users", "avatar_url", schema=schema)
