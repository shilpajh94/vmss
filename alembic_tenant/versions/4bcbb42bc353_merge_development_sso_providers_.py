"""merge development sso-providers migration with code-refactoring head

Revision ID: 4bcbb42bc353
Revises: 182a9231b5d5, 6f2a8c1d9e4b
Create Date: 2026-08-28 12:16:39.767227

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4bcbb42bc353"
down_revision: str | None = ("182a9231b5d5", "6f2a8c1d9e4b")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
