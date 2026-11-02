"""notification invitation fk and orphan purge

Revision ID: e6944d5e8ee2
Revises: cf04d5501383
Create Date: 2026-10-23 15:10:59.806501

Gives `notifications` a real `invitation_id` FK (`ON DELETE CASCADE`) in
place of the bare `data->>'invitationId'` string, and deletes the
notifications already orphaned by invitations hard-deleted before it
existed (prune-orphaned-notifications design.md D1/D4).

Order matters: backfill before the index so the `UPDATE` is cheap, and
delete orphans before the FK, which can't be added while they exist.
Downgrade drops the column but doesn't restore the deleted orphans — they
referenced invitations that no longer exist.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6944d5e8ee2"
down_revision: str | Sequence[str] | None = "cf04d5501383"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTERs on an existing table don't honor the connection's
    # `schema_translate_map`, so the target schema is passed explicitly —
    # same as f2a4c6e8b0d1.
    schema = op.get_context().version_table_schema
    op.add_column(
        "notifications", sa.Column("invitation_id", sa.Uuid(), nullable=True), schema=schema
    )
    conn = op.get_bind()
    # Compared as text so a malformed id in `data` can't abort the upgrade
    # with a uuid cast error.
    conn.execute(
        text(
            f'UPDATE "{schema}".notifications n SET invitation_id = i.id '
            f'FROM "{schema}".invitations i '
            "WHERE i.id::text = n.data->>'invitationId'"
        )
    )
    conn.execute(
        text(
            f'DELETE FROM "{schema}".notifications '
            "WHERE data ? 'invitationId' AND invitation_id IS NULL"
        )
    )
    op.create_index(
        op.f("ix_notifications_invitation_id"), "notifications", ["invitation_id"], schema=schema
    )
    op.create_foreign_key(
        "fk_notifications_invitation_id",
        "notifications",
        "invitations",
        ["invitation_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_constraint(
        "fk_notifications_invitation_id", "notifications", schema=schema, type_="foreignkey"
    )
    op.drop_index(op.f("ix_notifications_invitation_id"), table_name="notifications", schema=schema)
    op.drop_column("notifications", "invitation_id", schema=schema)
