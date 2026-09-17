"""merge poc and form-builder heads

Revision ID: f74620cd4ffa
Revises: c1d8e5f9a2b3, f1a2c7e9b3d5
Create Date: 2026-09-16 22:04:30.574453

`c1d8e5f9a2b3` (invitation point of contact) and `afb2544db111`'s branch
(form builder → `762e2a7cf5d1` → `f1a2c7e9b3d5`) were both authored with
`down_revision = "6f3a1c9d4e7b"` — chained off the same parent instead of
one after the other — so `alembic_tenant` diverged into two unmerged
heads with no revision reconciling them. That leaves
`command.upgrade(cfg, "head")`/`ScriptDirectory.get_current_head()`
raising `CommandError: Multiple head revisions are present` for any
tenant schema, which is why an existing tenant (e.g. `tenant_default`)
was stuck without the point-of-contact columns
(`fix-tenant-migration-branch-drift/proposal.md`).

Purely a graph-reconciliation revision — no schema change. Both branches
already carry their own DDL; this only gives them a single head so
`upgrade head` can apply whichever of the two a given environment is
still missing.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f74620cd4ffa"
down_revision: str | tuple[str, ...] | None = ("c1d8e5f9a2b3", "f1a2c7e9b3d5")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
