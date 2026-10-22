"""merge invitation approval-revert and devices heads

Revision ID: c9d2e4f6a8b1
Revises: 4ea4f6ccffbd, b7e1d3f5a9c2

Graph reconciliation only — no schema change.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c9d2e4f6a8b1"
down_revision: str | tuple[str, ...] | None = ("4ea4f6ccffbd", "b7e1d3f5a9c2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
