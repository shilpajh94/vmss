"""approval step host approver

Revision ID: a737ff0c6d62
Revises: a3f7c92e1d44
Create Date: 2026-08-31 00:00:00.000001

`add-approval-step-id-and-host-routing/design.md` Migration Plan step 1:
relaxes `invitation_approval_steps.approver_role_id` to nullable and adds a
nullable `approver_user_id` (FK `users.id`), so a step can name a specific
approving user (the invitation's host) instead of a role. A `CHECK`
constraint enforces exactly one of the two is set per row. Existing rows all
have `approver_role_id` set and `approver_user_id` null, so they already
satisfy the constraint — no backfill needed.

`invitation_approval_steps` already existed before this migration (created by
`a3f7c92e1d44`), so every statement here alters an existing table — `schema=`
must be passed explicitly throughout: `op.alter_column`/`op.add_column`/
`op.create_index`/`op.create_foreign_key`/`op.create_check_constraint` do not
pick up the connection's `schema_translate_map` the way `op.create_table`
does (same verified gotcha `a3f7c92e1d44`'s and `787f2f641092`'s docstrings
document).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a737ff0c6d62"
down_revision: str | None = "a3f7c92e1d44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPROVER_XOR_CONSTRAINT = "ck_invitation_approval_steps_approver_xor"
_TABLE = "invitation_approval_steps"


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.alter_column(
        _TABLE,
        "approver_role_id",
        existing_type=sa.Uuid(),
        nullable=True,
        schema=schema,
    )
    op.add_column(
        _TABLE,
        sa.Column("approver_user_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_index(
        op.f("ix_invitation_approval_steps_approver_user_id"),
        _TABLE,
        ["approver_user_id"],
        unique=False,
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitation_approval_steps_approver_user_id_users",
        _TABLE,
        "users",
        ["approver_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_check_constraint(
        _APPROVER_XOR_CONSTRAINT,
        _TABLE,
        "(approver_role_id IS NOT NULL) != (approver_user_id IS NOT NULL)",
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_constraint(_APPROVER_XOR_CONSTRAINT, _TABLE, schema=schema, type_="check")
    op.drop_constraint(
        "fk_invitation_approval_steps_approver_user_id_users",
        _TABLE,
        schema=schema,
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_invitation_approval_steps_approver_user_id"),
        table_name=_TABLE,
        schema=schema,
    )
    op.drop_column(_TABLE, "approver_user_id", schema=schema)
    op.alter_column(
        _TABLE,
        "approver_role_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema=schema,
    )
