"""org structure: scope unique code/number constraints to non-deleted rows

Revision ID: 880cf061a484
Revises: a1c9d4f7e2b0
Create Date: 2026-08-18 00:00:00.000000

Every unique constraint org_structure's tables had (`branches.code`,
`companies.registration_number`, `buildings(branch_id, code)`,
`floors(building_id, floor_number)`, `departments(floor_id, code)`,
`reception_desks(floor_id, code)`, `security_gates(branch_id, code)`) was
unconditional — it applied to soft-deleted rows too, even though every
create path's `get_by_code`/`get_by_number` pre-check (`repository.py`)
already filters `deleted_at IS NULL` before deciding a code is free.
Verified directly against Postgres (see
openspec/changes/harden-org-structure-crud/proposal.md) that this let a
soft-deleted row's code block the very next attempt to reuse it, failing
with an unhandled `IntegrityError` instead of the friendly 409 the
pre-check was clearly written to produce.

This migration drops each unconditional constraint/index and replaces it
with a unique index scoped to `deleted_at IS NULL`, matching the model
changes in `org_structure/models.py`. Strictly narrows what's enforced (a
soft-deleted row's code is not currently reserved a second time by any
existing code path), so no existing data can violate it.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` limitation as every migration in this tree (see
275bc2310f49's docstring).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "880cf061a484"
down_revision: str | None = "a1c9d4f7e2b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOT_DELETED = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.create_index(
        op.f("ix_branches_code"), "branches", ["code"], unique=True, postgresql_where=_NOT_DELETED
    )

    op.drop_constraint("companies_registration_number_key", "companies", type_="unique")
    op.create_index(
        "uq_companies_registration_number",
        "companies",
        ["registration_number"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint("uq_building_branch_code", "buildings", type_="unique")
    op.create_index(
        "uq_building_branch_code",
        "buildings",
        ["branch_id", "code"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint("uq_floor_building_number", "floors", type_="unique")
    op.create_index(
        "uq_floor_building_number",
        "floors",
        ["building_id", "floor_number"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint("uq_department_floor_code", "departments", type_="unique")
    op.create_index(
        "uq_department_floor_code",
        "departments",
        ["floor_id", "code"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint("uq_desk_floor_code", "reception_desks", type_="unique")
    op.create_index(
        "uq_desk_floor_code",
        "reception_desks",
        ["floor_id", "code"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )

    op.drop_constraint("uq_gate_branch_code", "security_gates", type_="unique")
    op.create_index(
        "uq_gate_branch_code",
        "security_gates",
        ["branch_id", "code"],
        unique=True,
        postgresql_where=_NOT_DELETED,
    )


def downgrade() -> None:
    op.drop_index("uq_gate_branch_code", table_name="security_gates")
    op.create_unique_constraint("uq_gate_branch_code", "security_gates", ["branch_id", "code"])

    op.drop_index("uq_desk_floor_code", table_name="reception_desks")
    op.create_unique_constraint("uq_desk_floor_code", "reception_desks", ["floor_id", "code"])

    op.drop_index("uq_department_floor_code", table_name="departments")
    op.create_unique_constraint("uq_department_floor_code", "departments", ["floor_id", "code"])

    op.drop_index("uq_floor_building_number", table_name="floors")
    op.create_unique_constraint(
        "uq_floor_building_number", "floors", ["building_id", "floor_number"]
    )

    op.drop_index("uq_building_branch_code", table_name="buildings")
    op.create_unique_constraint("uq_building_branch_code", "buildings", ["branch_id", "code"])

    op.drop_index("uq_companies_registration_number", table_name="companies")
    op.create_unique_constraint(
        "companies_registration_number_key", "companies", ["registration_number"]
    )

    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=True)
