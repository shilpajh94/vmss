"""tenant_badge_print_flow_toggle: per-tenant badge print flow switch

Revision ID: b7c1d4e9a2f3
Revises: 9f4a2e7c5d81
Create Date: 2026-11-02 00:00:00.000000

add-badge-print-flow: `tenants.badge_print_flow_enabled`, default false so
every existing tenant stays on the current behavior until an admin opts in.
Lives on the global `tenants` row because the flag is read before a tenant
session exists (`core/tenancy.py::get_tenant`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c1d4e9a2f3"
down_revision: str | None = "9f4a2e7c5d81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "global"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "badge_print_flow_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tenants", "badge_print_flow_enabled", schema=SCHEMA)
