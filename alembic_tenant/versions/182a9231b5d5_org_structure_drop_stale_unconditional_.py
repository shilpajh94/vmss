"""org structure: drop stale unconditional branches code unique constraint

Revision ID: 182a9231b5d5
Revises: 231748996893
Create Date: 2026-08-27 20:45:42.333449

`8f3b6a19d5e2` (the migration that first created `branches`) generated two
separate unique enforcements on `code` from one redundant model
declaration: `sa.UniqueConstraint('code')` (Postgres auto-named it
`branches_code_key`) *and* a hand-added `op.create_index(...,
'ix_branches_code', ..., unique=True)`. Every other org_structure table
(`companies`, `buildings`, `floors`, `departments`, `reception_desks`,
`security_gates`) only ever had one unique enforcement per code column, so
when `880cf061a484` replaced each unconditional unique
constraint/index with one scoped to `deleted_at IS NULL` (to let a
soft-deleted row's code be reused — see that migration's docstring), it
correctly swapped every other table's single constraint but only touched
`branches`' `ix_branches_code` half, missing the second, differently-named
`branches_code_key` constraint entirely. That leftover unconditional
constraint still enforces global uniqueness on `code` including
soft-deleted rows, reproducing the exact bug `880cf061a484` was written to
fix: soft-delete a branch, try to recreate one with the same `code`, get an
unhandled `IntegrityError` (surfaced as a 409 by
`org_structure/service.py::create_branch`'s `_commit_or_conflict`) instead
of being allowed to reuse the now-freed code.

`ix_branches_code` (the partial, `deleted_at IS NULL`-scoped index) already
enforces the intended uniqueness on its own, so this migration only drops
the redundant `branches_code_key` constraint — nothing to recreate.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` limitation as every migration in this tree (see
275bc2310f49's docstring).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "182a9231b5d5"
down_revision: str | None = "231748996893"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("branches_code_key", "branches", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("branches_code_key", "branches", ["code"])
