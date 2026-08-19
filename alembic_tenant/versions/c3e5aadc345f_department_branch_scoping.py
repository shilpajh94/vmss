"""org structure: department is scoped directly to a branch

Revision ID: c3e5aadc345f
Revises: 8313ae16aa5c
Create Date: 2026-08-19 00:00:01.000000

The admin design's department-creation flow assigns a department directly to
a Branch (a Branch dropdown, no Floor step), while the model only supported
department -> floor -> building -> branch. This migration adds a direct
`branch_id` FK to `departments`, backfills it from each row's existing
`floor_id`, makes `floor_id` optional, and moves the uniqueness scope from
`(floor_id, code)` to `(branch_id, code)`. See
openspec/changes/add-role-management-and-org-field-gaps/design.md Decision 4.

Backfill and the pre-check below use a real `sa.Table()` on a throwaway
`MetaData()`, not the lightweight `sa.table()` — `sa.table()` does not
participate in this connection's `schema_translate_map` and would silently
resolve against the connection's default search_path instead of the target
tenant schema (see 8f3b6a19d5e2's docstring for the same landmine hit
previously in this tree). Raw `text()` SQL is schema-qualified explicitly for
the same reason — it never respects `schema_translate_map` at all.

Every `add_column`/`alter_column`/`create_index`/`drop_index`/
`create_foreign_key` below targets a table that already existed before this
migration, so each passes `schema=` explicitly (275bc2310f49's landmine).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e5aadc345f"
down_revision: str | None = "8313ae16aa5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOT_DELETED = sa.text("deleted_at IS NULL")


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    bind = op.get_bind()

    op.add_column("departments", sa.Column("branch_id", sa.Uuid(), nullable=True), schema=schema)

    # Backfill: department -> floor -> building -> branch, schema-qualified
    # explicitly since raw text() never honors schema_translate_map.
    bind.execute(
        sa.text(
            f'UPDATE "{schema}".departments AS d '
            f'SET branch_id = b.branch_id '
            f'FROM "{schema}".floors AS f '
            f'JOIN "{schema}".buildings AS b ON b.id = f.building_id '
            f"WHERE d.floor_id = f.id"
        )
    )

    # Pre-check: uniqueness was previously scoped per-floor, so two
    # departments on different floors of the same branch may already share a
    # code — that's a real collision under the new (branch_id, code)
    # uniqueness this migration is about to enforce. Abort with a report
    # rather than let `CREATE UNIQUE INDEX` fail with an opaque constraint
    # violation, so a human can rename one of the colliding rows first.
    collisions = bind.execute(
        sa.text(
            f'SELECT branch_id, code, array_agg(id) AS ids '
            f'FROM "{schema}".departments '
            f"WHERE deleted_at IS NULL AND branch_id IS NOT NULL "
            f"GROUP BY branch_id, code "
            f"HAVING count(*) > 1"
        )
    ).fetchall()
    if collisions:
        details = "; ".join(
            f"branch {row.branch_id} code {row.code!r}: department ids {list(row.ids)}"
            for row in collisions
        )
        raise RuntimeError(
            "Cannot enforce (branch_id, code) uniqueness on departments — "
            f"the following departments already collide under the new branch-scoped "
            f"uniqueness rule and must be renamed first: {details}"
        )

    op.alter_column("departments", "branch_id", nullable=False, schema=schema)
    op.alter_column("departments", "floor_id", nullable=True, schema=schema)

    op.drop_index("uq_department_floor_code", table_name="departments", schema=schema)
    op.create_index(
        "uq_department_branch_code",
        "departments",
        ["branch_id", "code"],
        unique=True,
        schema=schema,
        postgresql_where=_NOT_DELETED,
    )
    op.create_index(
        op.f("ix_departments_branch_id"), "departments", ["branch_id"], unique=False, schema=schema
    )
    op.create_foreign_key(
        "fk_departments_branch_id",
        "departments",
        "branches",
        ["branch_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )

    op.add_column(
        "departments", sa.Column("head_of_department_user_id", sa.Uuid(), nullable=True), schema=schema
    )
    op.add_column(
        "departments", sa.Column("description", sa.String(length=2000), nullable=True), schema=schema
    )
    op.create_foreign_key(
        "fk_departments_head_of_department_user_id",
        "departments",
        "users",
        ["head_of_department_user_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    bind = op.get_bind()

    # A department created after the upgrade may have no floor_id at all
    # (the whole point of this change) — restoring floor_id as NOT NULL
    # would silently corrupt those rows. Refuse rather than guess.
    orphaned = bind.execute(
        sa.text(
            f'SELECT id FROM "{schema}".departments '
            f"WHERE deleted_at IS NULL AND floor_id IS NULL"
        )
    ).fetchall()
    if orphaned:
        ids = [row.id for row in orphaned]
        raise RuntimeError(
            "Cannot downgrade: the following departments have no floor_id and would "
            f"violate the restored NOT NULL constraint — assign a floor first: {ids}"
        )

    op.drop_constraint(
        "fk_departments_head_of_department_user_id",
        "departments",
        type_="foreignkey",
        schema=schema,
    )
    op.drop_column("departments", "description", schema=schema)
    op.drop_column("departments", "head_of_department_user_id", schema=schema)

    op.drop_constraint("fk_departments_branch_id", "departments", type_="foreignkey", schema=schema)
    op.drop_index(op.f("ix_departments_branch_id"), table_name="departments", schema=schema)
    op.drop_index("uq_department_branch_code", table_name="departments", schema=schema)
    op.create_index(
        "uq_department_floor_code",
        "departments",
        ["floor_id", "code"],
        unique=True,
        schema=schema,
        postgresql_where=_NOT_DELETED,
    )

    op.alter_column("departments", "floor_id", nullable=False, schema=schema)
    op.alter_column("departments", "branch_id", nullable=True, schema=schema)
    op.drop_column("departments", "branch_id", schema=schema)
