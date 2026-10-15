"""merge sms check-in code and devices heads

Revision ID: b7e1d3f5a9c2
Revises: a3c8e1d47b92, f2a4c6e8b0d1

Local stopgap: `a3c8e1d47b92` (SMS branch) and `f2a4c6e8b0d1` (devices) both
descend from `e5f7a9b1c3d4`. Graph reconciliation only — no schema change.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b7e1d3f5a9c2"
down_revision: str | tuple[str, ...] | None = ("a3c8e1d47b92", "f2a4c6e8b0d1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
