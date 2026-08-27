"""merge visit-info-lookup and employee-list-filters tenant migration heads

Revision ID: 231748996893
Revises: 2630a9b4c5f4, d6cca1692557
Create Date: 2026-08-27 12:55:14.742452

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "231748996893"
down_revision: str | None = ("2630a9b4c5f4", "d6cca1692557")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
