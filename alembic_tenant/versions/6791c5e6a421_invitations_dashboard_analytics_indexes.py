"""invitations: composite indexes for dashboard analytics

Revision ID: 6791c5e6a421
Revises: f7bd41138280
Create Date: 2026-10-16 00:00:00.000000

Additive only (live-dashboards-and-analytics design.md D4). The analytics
endpoints aggregate per branch over a date range on `preferred_visit_date`
(daily trend, status breakdown, top labels) and on `checked_in_at` (hourly
arrivals, checked-in-today), neither of which was indexed. Partial on
`deleted_at IS NULL`, matching every dashboard query's soft-delete filter.

`schema=` is passed explicitly: `create_index` on a pre-existing table
ignores `schema_translate_map` the same way `add_column` does.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6791c5e6a421"
down_revision: str | Sequence[str] | None = "f7bd41138280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOT_DELETED = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    op.create_index(
        "ix_invitations_branch_visit_date",
        "invitations",
        ["branch_id", "preferred_visit_date"],
        schema=schema,
        postgresql_where=_NOT_DELETED,
    )
    op.create_index(
        "ix_invitations_branch_checked_in_at",
        "invitations",
        ["branch_id", "checked_in_at"],
        schema=schema,
        postgresql_where=_NOT_DELETED,
    )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_index("ix_invitations_branch_checked_in_at", table_name="invitations", schema=schema)
    op.drop_index("ix_invitations_branch_visit_date", table_name="invitations", schema=schema)
