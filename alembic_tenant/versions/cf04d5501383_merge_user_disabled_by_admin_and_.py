"""merge user disabled by admin and trigram search heads

Revision ID: cf04d5501383
Revises: 14319832f01f, b3e9c1d7a5f4
Create Date: 2026-10-23 14:39:16.056182

`b3e9c1d7a5f4` (`users.disabled_by_admin`, from `openstack-dev`) and this
branch's `14319832f01f` (invitation trigram search indexes) were authored
on separate branches, leaving two tenant heads once merged.

Purely a graph-reconciliation revision — no schema change.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "cf04d5501383"
down_revision: str | tuple[str, ...] | None = ("14319832f01f", "b3e9c1d7a5f4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
