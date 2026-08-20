"""invitations: source column, nullable created_by_user_id

Revision ID: c3d8f21a9b6e
Revises: 2b57bd4b7d9d
Create Date: 2026-08-19 00:00:00.000000

API-13 (`add-walkin-visitor-registration`): a walk-in registration reuses the
`invitations` table (design.md Decision 1) instead of a parallel one. `source`
distinguishes "staff_pre_registration" (existing `POST /invitations` flow)
from "visitor_walk_in" (new `POST /registrations/walk-in` flow, no
authenticated staff creator — hence `created_by_user_id` becomes nullable).

Purely additive/relaxing: the new column has a server default so every
existing row backfills to "staff_pre_registration" without a separate data
migration, and dropping `NOT NULL` never invalidates an existing non-null
value.

Both statements below pass `schema=_target_schema()` explicitly — same
verified gotcha `275bc2310f49`'s docstring documents: `op.add_column`/
`op.alter_column` do NOT pick up the connection's `schema_translate_map` the
way `op.create_table` does, so without it they land on whatever schema is
first on the connection's plain `search_path` instead of the target tenant
schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d8f21a9b6e"
down_revision: str | None = "2b57bd4b7d9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.add_column(
        "invitations",
        sa.Column(
            "source",
            sa.String(length=30),
            nullable=False,
            server_default="staff_pre_registration",
        ),
        schema=schema,
    )
    op.alter_column(
        "invitations",
        "created_by_user_id",
        existing_type=sa.Uuid(),
        nullable=True,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.alter_column(
        "invitations",
        "created_by_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema=schema,
    )
    op.drop_column("invitations", "source", schema=schema)
