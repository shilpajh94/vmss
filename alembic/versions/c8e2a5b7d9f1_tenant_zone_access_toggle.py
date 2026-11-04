"""tenant_zone_access_toggle: per-tenant zone access control switch

Revision ID: c8e2a5b7d9f1
Revises: b7c1d4e9a2f3
Create Date: 2026-11-04 00:00:00.000000

add-zone-access-control: `tenants.zone_access_enabled`, default false so every
existing tenant is unchanged until an admin turns it on. Same shape and
reasoning as `b7c1d4e9a2f3` (lives on the global row because it is read before
a tenant session exists). Replaces the earlier `ZONE_ACCESS_ENABLED` env var.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8e2a5b7d9f1"
down_revision: str | None = "b7c1d4e9a2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "global"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "zone_access_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tenants", "zone_access_enabled", schema=SCHEMA)
