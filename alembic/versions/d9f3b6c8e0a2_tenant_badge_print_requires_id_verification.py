"""tenant_badge_print_requires_id_verification: optional ID check at badge print

Revision ID: d9f3b6c8e0a2
Revises: c8e2a5b7d9f1
Create Date: 2026-11-05 00:00:00.000000

optional-id-verification-for-badge-print: `tenants.badge_print_requires_id_verification`,
default true so every existing tenant keeps the current print gate. Lives on the
global row for the same reason as the other badge-flow toggle (read before a
tenant session exists).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9f3b6c8e0a2"
down_revision: str | None = "c8e2a5b7d9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "global"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "badge_print_requires_id_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("tenants", "badge_print_requires_id_verification", schema=SCHEMA)
