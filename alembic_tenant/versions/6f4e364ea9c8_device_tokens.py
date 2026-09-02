"""device tokens

Revision ID: 6f4e364ea9c8
Revises: a737ff0c6d62
Create Date: 2026-09-01 00:00:00.000000

`add-invitation-push-notifications/design.md` Migration Plan step 1: adds
`device_tokens`, one row per (user, physical device/browser) push
registration. Purely additive — no backfill needed, since a staff user's
first device registration populates their own row lazily.

`op.create_table` alone here (no `op.add_column`/`op.drop_column`), so it
already picks up the connection's `schema_translate_map` without an explicit
`schema=` kwarg — see `a3f7c92e1d44`'s docstring for the verified gotcha that
only bites `add_column`/`drop_column`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f4e364ea9c8"
down_revision: str | None = "a737ff0c6d62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("fcm_token", sa.String(length=4096), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_device_tokens_fcm_token"), "device_tokens", ["fcm_token"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_device_tokens_fcm_token"), table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_table("device_tokens")
