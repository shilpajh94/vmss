"""visitors: visitor category field additions

Revision ID: 39c3f5112585
Revises: 50d2e145f79f
Create Date: 2026-08-19 00:00:04.000000

Fills field gaps a design-vs-implementation review of the admin portal's
visitor-categories screen surfaced (see
openspec/changes/add-role-management-and-org-field-gaps/proposal.md):
badge color, NDA requirement, escort requirement, and max visit duration.
All nullable — purely additive, no backfill.

Passes `schema=` explicitly on `add_column` (275bc2310f49's landmine —
`op.add_column` does not honor `schema_translate_map` on an existing table
the way `op.create_table` does).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39c3f5112585"
down_revision: str | None = "50d2e145f79f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "visitor_categories",
        sa.Column("badge_color", sa.String(length=30), nullable=True),
        schema=schema,
    )
    op.add_column(
        "visitor_categories",
        sa.Column("nda_requirement", sa.String(length=20), nullable=True),
        schema=schema,
    )
    op.add_column(
        "visitor_categories",
        sa.Column("escort_requirement", sa.String(length=20), nullable=True),
        schema=schema,
    )
    op.add_column(
        "visitor_categories",
        sa.Column("max_duration_minutes", sa.Integer(), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("visitor_categories", "max_duration_minutes", schema=schema)
    op.drop_column("visitor_categories", "escort_requirement", schema=schema)
    op.drop_column("visitor_categories", "nda_requirement", schema=schema)
    op.drop_column("visitor_categories", "badge_color", schema=schema)
