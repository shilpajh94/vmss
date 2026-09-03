"""invitations: QR check-in security (encrypted token table, check_in_status)

Revision ID: 2cabb55d1de8
Revises: dfb1340caf66
Create Date: 2026-09-03 00:00:00.000000

`add-qr-checkin-security/design.md` — adds `invitation_qr_codes` (one row
per invitation, the encrypted token issued and where its rendered image was
persisted) and `invitations.check_in_status` (kept parallel to `status`,
default `unused` so every existing row backfills cleanly with no separate
data migration).

`op.add_column` passes `schema=_target_schema()` explicitly — it does not
pick up the connection's `schema_translate_map` the way `op.create_table`
does (same verified gotcha `787f2f641092`'s docstring documents).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2cabb55d1de8"
down_revision: str | None = "dfb1340caf66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.add_column(
        "invitations",
        sa.Column("check_in_status", sa.String(length=20), nullable=False, server_default="unused"),
        schema=schema,
    )

    op.create_table(
        "invitation_qr_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("qr_token", sa.String(length=500), nullable=False),
        sa.Column("image_storage_key", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_id"),
    )
    op.create_index(
        op.f("ix_invitation_qr_codes_invitation_id"),
        "invitation_qr_codes",
        ["invitation_id"],
        unique=True,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_index(
        op.f("ix_invitation_qr_codes_invitation_id"),
        table_name="invitation_qr_codes",
    )
    op.drop_table("invitation_qr_codes")
    op.drop_column("invitations", "check_in_status", schema=schema)
