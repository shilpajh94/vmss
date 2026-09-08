"""invitation reschedule history

Revision ID: 6f3a1c9d4e7b
Revises: 9a2f5c7e1b3d
Create Date: 2026-09-08 00:00:00.000001

`add-reschedule-history/design.md`: `PATCH /invitations/{id}/reschedule`
previously overwrote `preferred_visit_date`/`preferred_visit_time` in place
with no record of what the invitation was rescheduled from. Adds
`previous_preferred_visit_date`/`previous_preferred_visit_time` (the
immediately-prior date/time, snapshotted by `reschedule_if_eligible` in the
same `UPDATE` that sets the new ones), `rescheduled_at` (when the most
recent reschedule happened), and `reschedule_count` (how many times this
invitation has been rescheduled) — all nullable/zero-defaulted since no
existing row has ever been rescheduled under this column set.

`invitations` already existed before this migration, so `schema=` must be
passed explicitly on every statement — `op.add_column` does not pick up the
connection's `schema_translate_map` the way `op.create_table` does (same
verified gotcha `a737ff0c6d62`'s and `15d7580a57ed`'s docstrings document).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f3a1c9d4e7b"
down_revision: str | None = "9a2f5c7e1b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "invitations",
        sa.Column("previous_preferred_visit_date", sa.Date(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column("previous_preferred_visit_time", sa.Time(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column("rescheduled_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column(
            "reschedule_count", sa.Integer(), nullable=False, server_default="0"
        ),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_column("invitations", "reschedule_count", schema=schema)
    op.drop_column("invitations", "rescheduled_at", schema=schema)
    op.drop_column("invitations", "previous_preferred_visit_time", schema=schema)
    op.drop_column("invitations", "previous_preferred_visit_date", schema=schema)
