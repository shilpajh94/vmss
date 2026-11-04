"""kiosk_device_actor: device actor columns for the kiosk badge flow

Revision ID: f3b4c5d6e7a8
Revises: a7c3e5f19b24
Create Date: 2026-11-04 00:00:00.000000

add-kiosk-badge-print-flow: `badge_prints.printed_by_device_id` and
`invitations.id_verified_by_device_id`, both nullable FKs to `devices`.
`printed_by_user_id` is already nullable. A check constraint stops a print row
naming both a user and a device. Additive, so safe to apply before the code ships.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3b4c5d6e7a8"
down_revision: str | Sequence[str] | None = "a7c3e5f19b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `add_column`/FK/constraint ops don't go through `schema_translate_map`.
    schema = op.get_context().version_table_schema
    op.add_column(
        "badge_prints",
        sa.Column("printed_by_device_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_badge_prints_printed_by_device_id_devices",
        "badge_prints",
        "devices",
        ["printed_by_device_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_check_constraint(
        "ck_badge_prints_single_actor",
        "badge_prints",
        "num_nonnulls(printed_by_user_id, printed_by_device_id) <= 1",
        schema=schema,
    )
    op.add_column(
        "invitations",
        sa.Column("id_verified_by_device_id", sa.Uuid(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        "fk_invitations_id_verified_by_device_id_devices",
        "invitations",
        "devices",
        ["id_verified_by_device_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_constraint(
        "fk_invitations_id_verified_by_device_id_devices",
        "invitations",
        type_="foreignkey",
        schema=schema,
    )
    op.drop_column("invitations", "id_verified_by_device_id", schema=schema)
    op.drop_constraint("ck_badge_prints_single_actor", "badge_prints", type_="check", schema=schema)
    op.drop_constraint(
        "fk_badge_prints_printed_by_device_id_devices",
        "badge_prints",
        type_="foreignkey",
        schema=schema,
    )
    op.drop_column("badge_prints", "printed_by_device_id", schema=schema)
