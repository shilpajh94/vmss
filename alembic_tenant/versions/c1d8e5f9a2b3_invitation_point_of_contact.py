"""invitation point of contact

Revision ID: c1d8e5f9a2b3
Revises: 6f3a1c9d4e7b
Create Date: 2026-09-15 00:00:00.000001

`add-invitation-point-of-contact/design.md`: adds a point-of-contact pair to
`invitations`, distinct from the existing `host_id`/`host_name_or_email`
(the approval-workflow-resolved host) — `poc_user_id`/`poc_role_id` name who
to actually reach about the visit's logistics, settable directly via
`PATCH /invitations/{id}/edit` at any time, to either a specific person or a
role. `poc_name` snapshots the resolved display name (user's `full_name` or
role's `name`) the same way `host_name_or_email` already does, so rendering
it never needs an extra join.

At most one of `poc_user_id`/`poc_role_id` may be set (unlike
`invitation_approval_steps.approver_role_id`/`approver_user_id`'s
exactly-one XOR — see `a737ff0c6d62` — a point of contact is optional, so
both may be null).

`invitations` already existed before this migration, so `schema=` must be
passed explicitly on every statement — `op.add_column`/`op.create_index`/
`op.create_foreign_key`/`op.create_check_constraint` do not pick up the
connection's `schema_translate_map` the way `op.create_table` does (same
verified gotcha `a737ff0c6d62`'s and `6f3a1c9d4e7b`'s docstrings document).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d8e5f9a2b3"
down_revision: str | None = "6f3a1c9d4e7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POC_AT_MOST_ONE_CONSTRAINT = "ck_invitations_poc_at_most_one"
_TABLE = "invitations"


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(_TABLE, sa.Column("poc_user_id", sa.Uuid(), nullable=True), schema=schema)
    op.add_column(_TABLE, sa.Column("poc_role_id", sa.Uuid(), nullable=True), schema=schema)
    op.add_column(
        _TABLE, sa.Column("poc_name", sa.String(length=255), nullable=True), schema=schema
    )
    op.create_index(
        op.f("ix_invitations_poc_user_id"), _TABLE, ["poc_user_id"], unique=False, schema=schema
    )
    op.create_index(
        op.f("ix_invitations_poc_role_id"), _TABLE, ["poc_role_id"], unique=False, schema=schema
    )
    op.create_foreign_key(
        "fk_invitations_poc_user_id_users",
        _TABLE,
        "users",
        ["poc_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_poc_role_id_roles",
        _TABLE,
        "roles",
        ["poc_role_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_check_constraint(
        _POC_AT_MOST_ONE_CONSTRAINT,
        _TABLE,
        "(poc_user_id IS NULL) OR (poc_role_id IS NULL)",
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()

    op.drop_constraint(_POC_AT_MOST_ONE_CONSTRAINT, _TABLE, schema=schema, type_="check")
    op.drop_constraint(
        "fk_invitations_poc_role_id_roles", _TABLE, schema=schema, type_="foreignkey"
    )
    op.drop_constraint(
        "fk_invitations_poc_user_id_users", _TABLE, schema=schema, type_="foreignkey"
    )
    op.drop_index(op.f("ix_invitations_poc_role_id"), table_name=_TABLE, schema=schema)
    op.drop_index(op.f("ix_invitations_poc_user_id"), table_name=_TABLE, schema=schema)
    op.drop_column(_TABLE, "poc_name", schema=schema)
    op.drop_column(_TABLE, "poc_role_id", schema=schema)
    op.drop_column(_TABLE, "poc_user_id", schema=schema)
