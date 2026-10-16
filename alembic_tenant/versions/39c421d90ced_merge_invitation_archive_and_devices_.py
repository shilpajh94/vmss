"""merge invitation archive/auto-checkout and devices heads

Revision ID: 39c421d90ced
Revises: ee5f27776d94, c9d2e4f6a8b1

Graph reconciliation only — no schema change.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "39c421d90ced"
down_revision: str | tuple[str, ...] | None = ("ee5f27776d94", "c9d2e4f6a8b1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
