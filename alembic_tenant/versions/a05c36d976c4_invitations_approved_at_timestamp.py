"""invitations: approved at timestamp

Revision ID: a05c36d976c4
Revises: 39c3f5112585
Create Date: 2026-08-24 16:20:01.824209

Records when an invitation's status transitions to "approved" — either
resolved immediately at creation
(`Company.auto_approve_pre_registered_visitors`) or later via
`POST /invitations/{id}/approve` (see
openspec/changes/add-invitation-approval-flow-and-role-resync/design.md
Decision 4). Nullable, no backfill — every existing row is treated as
never-approved (`NULL`) regardless of its current `status` value.

Passes `schema=` explicitly on `add_column` (275bc2310f49's landmine —
`op.add_column` does not honor `schema_translate_map` on an existing table
the way `op.create_table` does).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a05c36d976c4"
down_revision: str | None = "39c3f5112585"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("invitations", "approved_at", schema=schema)
