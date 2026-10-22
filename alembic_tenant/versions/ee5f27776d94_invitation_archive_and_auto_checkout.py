"""invitation archive state and automatic check-out flag

Revision ID: ee5f27776d94
Revises: 4ea4f6ccffbd
Create Date: 2026-10-15 00:00:00.000000

`auto-checkout-and-archive-no-shows` adds `archived_at` (set when the
visit-lifecycle sweep archives an approved no-show) and
`checked_out_automatically` (set when the sweep closes an expired check-in).
No backfill: the first sweep after deploy processes existing stale rows.

Downgrade first returns `archived` rows to `approved` — older code doesn't
know the status, and those rows are already expired so they stay inert.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee5f27776d94"
down_revision: str | Sequence[str] | None = "4ea4f6ccffbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column(
            "checked_out_automatically",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.get_bind().execute(
        text(f"UPDATE \"{schema}\".invitations SET status = 'approved' WHERE status = 'archived'")
    )
    op.drop_column("invitations", "archived_at", schema=schema)
    op.drop_column("invitations", "checked_out_automatically", schema=schema)
