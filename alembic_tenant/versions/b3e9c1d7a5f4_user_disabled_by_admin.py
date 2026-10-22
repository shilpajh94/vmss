"""auth: user disabled_by_admin flag

Revision ID: b3e9c1d7a5f4
Revises: a7c3e1d9b5f2
Create Date: 2026-10-19 00:00:00.000000

Distinguishes an employee an admin disabled on purpose from one directory
sync deactivated by omission, so a later sync batch doesn't silently
re-enable the former. Purely additive; existing rows default to false.

Passes `schema=` explicitly on `add_column` (275bc2310f49's landmine).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e9c1d7a5f4"
down_revision: str | None = "a7c3e1d9b5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "users",
        sa.Column(
            "disabled_by_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("users", "disabled_by_admin", schema=schema)
