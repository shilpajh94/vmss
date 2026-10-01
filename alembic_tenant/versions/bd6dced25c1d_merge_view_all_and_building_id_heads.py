"""merge view-all and building_id heads

Revision ID: bd6dced25c1d
Revises: d4e6f8a0b2c3, d4e9a2b7c1f6
Create Date: 2026-10-01 10:40:47.405959

Merging `development` into `feature/fix-optimisation` left two tenant heads,
both descending from `b7c2e9a4d1f3`:
`c3d5e7f9a1b2` -> `d4e6f8a0b2c3` (grant `invitations:view-all`) and
`c3d8f1a6b2e4` -> `d4e9a2b7c1f6` (`invitations.building_id`). This no-op
revision joins them so `upgrade head` is unambiguous again. The two branches
touch unrelated tables (`role_permissions` vs `invitations`), so their
relative order doesn't matter.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "bd6dced25c1d"
down_revision: str | Sequence[str] | None = ("d4e6f8a0b2c3", "d4e9a2b7c1f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
