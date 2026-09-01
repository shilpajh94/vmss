"""approval step delegation

Revision ID: 15d7580a57ed
Revises: 6f4e364ea9c8
Create Date: 2026-09-01 00:00:00.000001

`invitation-relevant-to-me-and-delegation/design.md` Decision "Add
delegated_to_user_id / delegated_by_user_id / delegated_at columns rather
than repurposing approver_user_id": adds three nullable columns to
`invitation_approval_steps` recording who a role-identified step was
delegated to by the host, by whom, and when. No backfill needed — every
existing row has no delegation.

`invitation_approval_steps` already existed before this migration, so every
statement here alters an existing table — `schema=` must be passed
explicitly throughout: `op.add_column`/`op.create_index`/
`op.create_foreign_key` do not pick up the connection's
`schema_translate_map` the way `op.create_table` does (same verified gotcha
`a737ff0c6d62`'s docstring documents).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15d7580a57ed"
down_revision: str | None = "6f4e364ea9c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "invitation_approval_steps"


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        _TABLE,
        sa.Column("delegated_to_user_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.add_column(
        _TABLE,
        sa.Column("delegated_by_user_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.add_column(
        _TABLE,
        sa.Column("delegated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_index(
        op.f("ix_invitation_approval_steps_delegated_to_user_id"),
        _TABLE,
        ["delegated_to_user_id"],
        unique=False,
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitation_approval_steps_delegated_to_user_id_users",
        _TABLE,
        "users",
        ["delegated_to_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_invitation_approval_steps_delegated_by_user_id_users",
        _TABLE,
        "users",
        ["delegated_by_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_constraint(
        "fk_invitation_approval_steps_delegated_by_user_id_users",
        _TABLE,
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_invitation_approval_steps_delegated_to_user_id_users",
        _TABLE,
        schema=schema,
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_invitation_approval_steps_delegated_to_user_id"),
        table_name=_TABLE,
        schema=schema,
    )
    op.drop_column(_TABLE, "delegated_at", schema=schema)
    op.drop_column(_TABLE, "delegated_by_user_id", schema=schema)
    op.drop_column(_TABLE, "delegated_to_user_id", schema=schema)
